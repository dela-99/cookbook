# Stream a 1GB Video File

Serve massive video files without crashing your server's RAM — by streaming in chunks using a generator.

## The Idea

Instead of loading an entire 1GB file into memory, you use a **generator** that reads the file in small 1MB chunks and yields them one at a time.

Here's what happens on every request:

1. Client requests `/video`
2. Server opens the file and reads 1MB
3. That chunk is sent to the client immediately
4. Memory is freed, next chunk is read
5. Repeat until the file is fully streamed

Your RAM stays flat regardless of file size. Even with 1,000 concurrent viewers, each request only holds ~1MB in memory.

## Why `yield` Instead of Returning the File?

`yield` creates a generator. It reads 1MB, sends it to the client, clears it, and repeats. If the user pauses or closes the tab, the generator stops instantly — the connection closes, the file handle is released, and no resources are wasted.

## What About Seeking (Skipping to the Middle)?

This basic implementation streams from the beginning. For full seek support, you'd implement **HTTP Range Headers** — letting the browser request specific byte ranges instead of the whole stream.

## Run

```bash
uv run uvicorn main:app --reload
```

## Test

Place a video file named `large_video.mp4` in the project directory, then open in your browser:

```
http://localhost:8000/video
```

The browser starts playing as soon as the first chunks arrive thanks to the `media_type="video/mp4"` header.

## In Production

This demo streams from the local filesystem. In a real production system you'd stream from object storage (S3, GCS), add HTTP Range Header support for seeking, and put a CDN in front for caching — same streaming pattern, just a different source and more headers.
