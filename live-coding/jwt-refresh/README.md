# JWT Refresh (Token Rotation)

Stop hackers from owning your users forever — even if they steal a token.

## The Idea

A stolen token that never expires = permanent account takeover. The fix is **token rotation**: tokens are short-lived, and every time you refresh, the old token is destroyed.

Two tokens are issued at login:

| Token | Lives for | Purpose |
|---|---|---|
| `access_token` | 15 minutes | Authenticate every request |
| `refresh_token` | 7 days | Get a new access token when the old one expires |

Think of it like a hotel:

- **Room key** (access token) — works for 15 minutes, then it stops working
- **Voucher** (refresh token) — you hand it in to get a new key and a new voucher
- **Critical rule** — once a voucher is handed in, it is **shredded**. If someone shows up with the same voucher again, the front desk knows it was stolen and cancels _everything_.

Here's what happens on every `/refresh` call:

1. Check if this refresh token was already used → if yes, it's a replay attack
2. Revoke all sessions for that user (nuclear option)
3. Decode the token to read the user ID
4. **Burn** the old refresh token in Redis (TTL = 7 days, same as its expiry)
5. Issue a fresh `access_token` + `refresh_token` pair

## How Theft Detection Works

```
Normal flow:
  User → POST /refresh (voucher A) → gets key B + voucher B
  Voucher A is now burned in Redis

Stolen token scenario:
  Hacker steals voucher A, redeems it first → gets key B + voucher B
  Voucher A is now burned

  User shows up with voucher A → Redis says it was already used → ALARM
  Server revokes ALL sessions for this user → hacker's key B stops working too
```

The attacker wins the first exchange, but the moment the real user tries to refresh, both parties get locked out and the user is forced to log in again. The attack window is closed.

## Routes

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/login` | No | Returns access token + refresh token |
| `POST` | `/refresh` | No (sends refresh token in body) | Rotates both tokens |
| `GET` | `/me` | Yes (`Authorization: Bearer <access_token>`) | Protected route example |

## Run

```bash
uv run uvicorn main:app --reload
```

## Test

Run these commands in order to see the full rotation flow.

**Step 1 — Login and grab your tokens:**

```bash
LOGIN=$(curl -s -X POST "http://localhost:8000/login?user_id=alice")
ACCESS=$(echo $LOGIN | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH=$(echo $LOGIN | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "Access:  $ACCESS"
echo "Refresh: $REFRESH"
```

**Step 2 — Hit the protected route with your access token:**

```bash
curl -s -H "Authorization: Bearer $ACCESS" http://localhost:8000/me
# → {"user_id": "alice", "message": "Access granted."}
```

**Step 3 — Rotate your tokens (normal refresh):**

```bash
NEW=$(curl -s -X POST http://localhost:8000/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH\"}")
echo $NEW
NEW_ACCESS=$(echo $NEW | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
NEW_REFRESH=$(echo $NEW | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
```

**Step 4 — Replay the old refresh token (simulate stolen token):**

```bash
curl -s -X POST http://localhost:8000/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH\"}"
# → 401: "Stolen token detected. All sessions revoked. Please log in again."
```

**Step 5 — Confirm the new tokens are also revoked:**

```bash
curl -s -H "Authorization: Bearer $NEW_ACCESS" http://localhost:8000/me
# → 401: "Session revoked. Please log in again."
```

## In Production

This demo uses `fakeredis` — an in-memory Redis substitute that requires no setup. In production, swap it for a real Redis instance:

```python
# pyproject.toml: add "redis" to dependencies
import redis
r = redis.Redis(host="your-redis-host", port=6379, decode_responses=True)
```

Also set `SECRET_KEY` as an environment variable — never hardcode it:

```bash
export SECRET_KEY="a-long-random-string-from-a-secrets-manager"
```
