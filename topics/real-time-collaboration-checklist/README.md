# Real-Time Collaboration App — Pre-Launch Checklist

Real-time collaboration apps fail in characteristic ways. Two users see different versions of the same document. An edit lands on one client and quietly disappears from another. The presence indicator says "Alice is online" for 30 seconds after Alice closed the tab. A WebSocket server rotates during a deploy and a thousand rooms silently desync.

Most of these failures aren't bugs in the obvious places — they're **missing architectural decisions**. This checklist walks the seven things you must answer before shipping a real-time collaboration app to production.

## 1. Edit Synchronization — WebSockets + CRDTs

**What it means.** Two users typing in the same document need their edits to merge automatically, without one overwriting the other. **WebSockets** give you the bidirectional, low-latency channel. **CRDTs** (Conflict-free Replicated Data Types) give you the merge algorithm — every client converges on the same final document regardless of edit order or network delay.

**Why it matters before launch.** If you build sync on top of REST polling, the app feels laggy — cursor positions update in 3-second jumps and users notice immediately. If you "merge" with last-write-wins, you silently lose data — a user types two paragraphs while another reformats the heading, and one of those edits vanishes. CRDTs (Y.js, Automerge) are the production-grade answer. The alternative is Operational Transform (Google Docs), which works but is famously brutal to implement correctly.

## 2. Authentication — Short-Lived JWTs + Revocable Refresh Tokens

**What it means.** Every WebSocket connection and every API call must prove who the user is. Use short-lived access tokens (15-minute JWTs) on every request, and long-lived refresh tokens (7-day, server-side revocable) to rotate the access token without forcing the user to log in again.

**Why it matters before launch.** A stolen long-lived JWT is a permanent account takeover — there's no way to revoke it. A WebSocket that doesn't re-validate its token on every reconnect leaves logged-out users still receiving live updates. See [JWT Refresh (Token Rotation)](../../live-coding/jwt-refresh/) for the full working implementation.

## 3. Authorization — Per-Document, Per-User Permissions

**What it means.** Authentication says *who* you are. Authorization says *which documents you can read, edit, comment on, or share*. Every WebSocket `subscribe`, every snapshot read, and every delta write must check that the requesting user has the right role on **that specific document** — not just "is logged in to the app."

**Why it matters before launch.** Without per-document authz, any authenticated user can join any room whose ID they discover. Document IDs leak through shareable URLs, email forwards, screenshots, and browser history — and the moment one leaks without an ownership check, anyone with a valid login can join the room and read live keystrokes. This is the same **IDOR** class of bug from the [Pre-Deployment Checklist](../pre-deployment-checklist/) — just applied to live collaboration, where the leak shows up as keystrokes streaming in real time.

## 4. Presence — Cursors, Avatars, "Who's Here Right Now"

**What it means.** A **presence channel** broadcasts ephemeral state — who's currently in the room, where each cursor is, who's typing. Unlike document state, presence is throwaway: when the user disconnects, their presence evaporates within seconds.

**Why it matters before launch.** Presence is what makes a collab app *feel* alive instead of feeling like a Google Form. But it's also a performance trap — cursor positions sent on every keystroke can saturate the WebSocket layer at scale. Throttle cursor updates to ~30/sec per user, debounce typing indicators, and **never persist presence to the database** — it's noise, not data.

## 5. Document State — Snapshots in Postgres, Deltas in Redis

**What it means.** Persist the **committed state** of each document as periodic snapshots in Postgres — durable, queryable, backed up. Stream the **recent edits** (deltas) through Redis for fast, low-latency access. On a schedule (e.g., every N deltas or every M minutes), compact accumulated Redis deltas into a fresh Postgres snapshot.

**Why it matters before launch.** If every keystroke hits Postgres, your write throughput collapses under any real load. If the entire document lives in Redis, a Redis failure loses everything not yet snapshotted. The snapshot + delta pattern is how you get fast reads, fast writes, **and** durability — three things that are otherwise at war with each other.

## 6. Crash Recovery — Sticky Sessions + Auto-Reconnect + Resume from Last Delta

**What it means.** When a WebSocket server crashes (or just rotates during a deploy), the client must:

1. **Detect the disconnect** immediately and surface it in the UI
2. **Reconnect to the same logical room** via sticky session routing (or via room-aware load balancing)
3. **Resume from the last delta number** it saw — receive only the deltas it missed, not the entire document

**Why it matters before launch.** Without sticky sessions, the reconnecting client lands on a different server that doesn't know about its room — silent state divergence between clients in the same document. Without delta resume, every reconnect re-downloads the full document — punishing UX and your egress bill. Without auto-reconnect, a 200ms blip becomes "connection lost, please refresh" and a lost edit.

## 7. Horizontal Scaling — Redis Pub/Sub Per Room

**What it means.** A single WebSocket server can only hold so many concurrent connections (typically tens of thousands). Scale horizontally by running many servers and treating **each room as its own Redis pub/sub channel**. Every server subscribes to the channels for the rooms its connected clients are in; a write on one server publishes through Redis and fans out to every other server hosting clients for that room.

**Why it matters before launch.** Without a pub/sub layer, scaling means every server has to talk to every other server — N² connection complexity that fails by the time you have a dozen servers. With pub/sub, the message bus becomes the only thing that has to scale, and individual servers stay stateless and simple. This is how Slack, Figma, and Linear scale to millions of concurrent rooms.

---

## TL;DR

Before you ship a real-time collaboration app, walk the checklist:

1. **Edit sync** — WebSockets + CRDTs, never REST polling, never last-write-wins
2. **Authentication** — short-lived JWTs + revocable refresh tokens, re-validated on every reconnect
3. **Authorization** — per-document, per-user checks on every subscribe / read / write
4. **Presence** — throttled, debounced, ephemeral; never persisted
5. **Document state** — snapshots in Postgres + deltas in Redis, compacted on a schedule
6. **Crash recovery** — sticky sessions + auto-reconnect + resume from last delta number
7. **Horizontal scaling** — one Redis pub/sub channel per room, servers stateless

If any of these is a "we'll figure it out after launch," that's the one that takes down your first viral demo.

---

## Resources

### Docs
- [Y.js — CRDT framework for collaborative apps](https://yjs.dev)
- [Automerge — alternative CRDT implementation](https://automerge.org)
- [Redis Pub/Sub](https://redis.io/docs/latest/develop/interact/pubsub/)
