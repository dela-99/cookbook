# Designing Google Drive

## The Interview Question

> "Design Google Drive."

The instinct: "Easy — a backend server, a database for the files."

```python
@app.post("/upload")
def upload(file):
    db.execute("INSERT INTO files (name, data) VALUES (?, ?)", file.name, file.read())
```

Then the kill-shot:

> "So you're going to push raw video and image files straight into SQL tables?"

The whole answer collapses. Because the moment you store a 4GB video as a BLOB in your relational database, you've turned your transactional database into a file server — and it's catastrophically bad at that job.

This is the interview question that tests whether you understand a single principle most engineers miss: **the database is for what you query, not what you store.**

---

## Attempt 1 — Files in the Database (Why It Fails)

Putting binary file data in a SQL table is wrong for reasons that compound:

| Problem | What happens |
|---|---|
| **Row size** | A single 4GB video row blows past every reasonable page size. The database has to handle out-of-band storage internally — slower than just using a file system. |
| **Backup cost** | Every database backup now copies every video. Your nightly snapshot of "user metadata" is suddenly 50TB. |
| **Replication lag** | Every write replicates the entire payload to read replicas. A single 1GB upload can stall replication for minutes. |
| **Buffer pool pollution** | The DB cache is full of video bytes, evicting the small hot rows your actual queries need. |
| **Cost per GB** | Database storage is 5–10× more expensive per GB than object storage. You're paying premium prices to do the worst-fit job possible. |

The interview is over if you stop here.

---

## Attempt 2 — Metadata in SQL, Files in Object Storage

The fix: split the *information about the file* from the *file itself*.

```
┌─────────────┐                        ┌──────────────────┐
│   SQL DB    │                        │   Blob Storage   │
│             │                        │  (Azure/S3/GCS)  │
│  files:     │                        │                  │
│  id         │                        │   abc123.mp4     │
│  user_id    │  ──── points to ────▶  │   def456.jpg     │
│  name       │                        │   ghi789.pdf     │
│  size       │                        │                  │
│  blob_key   │                        │                  │
└─────────────┘                        └──────────────────┘
```

Now SQL stores rows that are a few hundred bytes each. Object storage holds the giant files — and that's *its job*. S3, Azure Blob, and Google Cloud Storage are designed for petabytes of unstructured data at low cost per GB.

But there's still a problem: **how does the file actually get from the user's device into blob storage?**

The naive answer: "The user uploads to our API server, and our API server forwards the file to blob storage."

Then the next kill-shot:

> "Your API servers will suffer handling millions of giant uploads at the same time."

Every byte still flows through your backend. A million users each uploading a 1GB video means your fleet is temporarily a 1PB throughput pipe. Your CPU is fine, your code is fine — your **bandwidth and memory** are dead.

---

## The Real Pattern — Pre-Signed URLs

The trick that wins the interview: **your backend never touches the file payload.**

A **pre-signed URL** (Azure calls it a *SAS token*, AWS calls it a *pre-signed S3 URL*) is a temporary, scoped, signed URL that grants permission to upload to (or download from) a specific blob in cloud storage — **without** the client needing the storage account's credentials.

Here's the flow:

```
1.  Client          →  POST /upload-permission   →  Backend
2.  Backend creates a SQL row, generates a pre-signed URL, returns it
3.  Client          →  PUT <pre-signed-url>      →  Azure Blob Storage
                       (file streams directly, no backend involved)
4.  Client          →  POST /confirm-upload      →  Backend
5.  Backend marks the row as "uploaded"
```

Your API server's only job is to **authorize** the upload — issue a signed URL with a 15-minute expiry and a scope of "this one blob key, write-only." The actual bytes go directly from the client's network to the cloud provider's network. Your server stays a tiny coordination layer that never sees a single video frame.

---

## How a Pre-Signed URL Actually Works

A pre-signed URL is a regular HTTPS URL with extra query parameters that prove it was authorized:

```
https://mystorage.blob.core.windows.net/uploads/abc123.mp4
  ?sig=<HMAC-signed-string>
  &se=2026-05-27T14:00:00Z       (expiry timestamp)
  &sp=w                          (permission: write only)
  &sr=b                          (scope: blob only)
```

Azure (or AWS) validates the signature against the storage account key. If it matches and hasn't expired, the upload is allowed. **The signature is computed by your backend using a key the client never sees.** The client receives a URL it can use for 15 minutes — and only for the one blob you specified.

This is why pre-signed URLs are safe: they're **short-lived** and **scoped to a single resource and operation**. Even if a URL leaks, it's useless after expiry, and useless for anything except that one blob.

---

## Downloads Use the Same Trick

Downloads work identically — flipped:

```
1.  Client          →  GET /file/123            →  Backend
2.  Backend checks SQL (does this user have read access?)
3.  Backend generates a pre-signed download URL (read-only, 15-min expiry)
4.  Backend         →  302 Redirect             →  Client
5.  Client          →  GET <pre-signed-url>     →  Azure Blob Storage
                       (file streams directly)
```

Your backend authorizes the read by checking the metadata in SQL — "does user 42 own file 123, or has it been shared with them?" — then hands back a URL the client uses directly. Bandwidth cost on your servers: zero.

---

## The Hotel Key Card Analogy

A pre-signed URL is a hotel key card.

- The **front desk** (your backend) verifies your identity, takes payment, and decides which room you can enter.
- The **key card** (the pre-signed URL) opens *one specific room*, for a *limited time*, and only lets you do *one specific thing* (enter, not modify the room itself).
- You walk to the room and unlock it yourself. The front desk staff never carries your bags — they just authorize who gets which key.

If the database were the hotel, putting files in SQL is asking the front desk to personally carry every guest's luggage to every room. They burn out fast.

---

## Why This Scales

| Component | What it does | Scales by |
|---|---|---|
| **API server** | Auth + metadata writes + URL signing | Standard horizontal scaling — it's just JSON in/out |
| **SQL database** | Stores file metadata only | Postgres handles billions of small rows comfortably |
| **Blob storage** | Stores the actual files | Effectively infinite — built for exabytes |
| **Client ↔ Storage** | The file transfer itself | Bypasses your stack entirely; uses the cloud provider's CDN-grade network |

A handful of small backend servers can authorize millions of concurrent uploads — because all they do is sign URLs. The heavy lifting happens between the client and the cloud provider's storage, on infrastructure you didn't build and don't have to scale.

---

## Production Considerations

| Decision | What to think about |
|---|---|
| **URL expiry** | 5–15 minutes is the usual range. Too short and slow connections fail mid-upload. Too long and a leaked URL becomes a security incident. |
| **Multipart uploads** | Files larger than ~100MB should use multipart upload — the client uploads in chunks, each with its own pre-signed URL. Resumable, parallelizable, recoverable. |
| **Don't trust the client's confirmation** | If the client crashes mid-upload, your `/confirm-upload` never fires. Use Azure Event Grid / S3 event notifications so blob storage tells *you* when an upload finished. |
| **Virus scanning** | Files arriving directly in blob storage never pass through your servers — meaning no antivirus middleware ran. Use post-upload scanning (Azure Defender, ClamAV in a Lambda) triggered by blob events. |
| **CDN for downloads** | Pair blob storage with a CDN for read-heavy content (images, videos). The download URL points to the CDN, which fronts the blob — see [CDN Anycast Routing](../cdn-anycast-routing/). |
| **Pre-signed URL leakage** | A leaked URL works for anyone until it expires. For sensitive content, scope tighter (5-minute expiry, IP-restricted SAS tokens). |

---

## The Key Insight

The database is for **what you query**, not **what you store**.

You query "list the files in this folder owned by user 42" — that's metadata. You don't query "the third byte of frame 1,247 of this video" — that's a file. Files belong in blob storage, metadata belongs in SQL, and the two should be linked by a key column — not crammed into the same system.

Once your files are in blob storage, the single biggest scaling move is to **stop touching them**. Pre-signed URLs turn your backend from a file pipe into a permission desk. Permission desks scale. File pipes don't.

---

## TL;DR

- **Never store files in SQL.** Use the database for metadata (name, size, owner, blob key). Use object storage (S3, Azure Blob, GCS) for the file bytes.
- **Never pipe uploads through your API server.** Use **pre-signed URLs** (Azure SAS tokens, S3 pre-signed URLs) so the client uploads directly to blob storage.
- The backend's job is to **authorize** — write the metadata row, sign a URL scoped to that one blob with a 5–15 minute expiry, and hand it to the client.
- Downloads use the same trick reversed: backend checks permission, returns a short-lived signed URL, client pulls directly from storage.
- A handful of small backend servers can serve millions of concurrent file transfers because they never touch the bytes.

When the interviewer says "design Google Drive," the answer isn't about disk space or schemas. It's about **who carries the file** — and the right answer is "not my server."

---

## Related

- [Designing Google Docs](../design-google-docs/) — the collaborative-editing counterpart in the "designing X" system design series
- [CDN Anycast Routing](../cdn-anycast-routing/) — how downloads get even faster once the file is in blob storage

---

## Resources

### Docs
- [Azure — Shared Access Signatures (SAS) overview](https://learn.microsoft.com/azure/storage/common/storage-sas-overview)
- [AWS — Sharing objects with pre-signed URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
- [Google Cloud — Signed URLs](https://cloud.google.com/storage/docs/access-control/signed-urls)
- [Azure Blob Storage — Event Grid notifications](https://learn.microsoft.com/azure/storage/blobs/storage-blob-event-overview)
