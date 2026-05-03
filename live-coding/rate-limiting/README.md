# Rate Limiting

Stop bots from spamming your API using rate limiting with a single decorator.

## The Idea

Instead of letting anyone hit your endpoints unlimited times, you set a **threshold per user** (identified by IP). Once they exceed it, they get a `429 Too Many Requests` and the request never reaches your business logic.

Here's what happens:

1. Request comes in → `slowapi` identifies the user by IP
2. Checks how many requests that IP has made in the time window
3. Under the limit → request goes through normally
4. Over the limit → instantly returns `429`, no compute wasted

You can set different limits per route:

- `/login` → 5 requests/minute (prevent brute force)
- `/products` → 100 requests/minute (normal browsing)
- `/reset-password` → 3 requests/minute (sensitive action)

## How It Works Under the Hood

`slowapi` uses the **Token Bucket** algorithm. Each user gets a bucket of tokens that refills over time. Every request costs one token. Empty bucket = rejected.

## Run

```bash
uv run uvicorn main:app --reload
```

## Test

```bash
# Hit login 6 times rapidly — the 6th will return 429
for i in $(seq 1 6); do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/login; done
```

## In Production

This demo uses in-memory storage for rate limit counters. In production with multiple server instances, you'd use a shared backend like **Redis** so limits are enforced across all servers consistently.
