import os
from datetime import datetime, timedelta, timezone

import fakeredis
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

SECRET = os.getenv("SECRET_KEY", "super-secret-dev-key")
ALGORITHM = "HS256"

app = FastAPI()
security = HTTPBearer()

# In production, swap this for redis.Redis(host="your-redis-host")
r = fakeredis.FakeRedis()

# ── Token helpers ─────────────────────────────────────────────────────────────


def create_access_token(user_id: str) -> str:
    """Short-lived token (15 min) — used to authenticate requests."""
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Long-lived token (7 days) — used only to get a new access token."""
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def revoke_all_sessions(user_id: str) -> None:
    """Nuclear option — marks the user as globally logged out in Redis.
    Any request from this user will be rejected until they log in again."""
    r.setex(f"revoked_user:{user_id}", 7 * 24 * 3600, "1")


# ── Schemas ───────────────────────────────────────────────────────────────────


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Routes ────────────────────────────────────────────────────────────────────


@app.post("/login")
async def login(user_id: str = "alice"):
    """Simulate a login — issues an access token + refresh token pair.

    In a real app this would validate username/password first.
    """
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
    }


@app.post("/refresh")
async def rotate_tokens(body: RefreshRequest):
    """Token rotation — the core of JWT security.

    Hotel analogy:
    - access_token  = room key   (works for 15 min)
    - refresh_token = voucher    (lets you get a new key when it expires)

    Flow:
    1. Check if this voucher was already used → stolen token alarm.
    2. Decode the token to read the user ID.
    3. Burn (shred) the old refresh token so it can NEVER be used again.
    4. Issue a brand-new access token + refresh token pair.
    """
    refresh_token = body.refresh_token

    # ── Step 1: Replay detection ───────────────────────────────────────────
    # If this token exists in the "burned" set, someone already redeemed it.
    # That means either the user is replaying an old token, OR a hacker
    # stole it and used it first. Either way — revoke everything.
    if r.get(f"burned:{refresh_token}"):
        try:
            payload = jwt.decode(refresh_token, SECRET, algorithms=[ALGORITHM])
            revoke_all_sessions(payload["sub"])
        except jwt.PyJWTError:
            pass  # Token is malformed but was somehow in Redis — still reject
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Stolen token detected. All sessions revoked. Please log in again.",
        )

    # ── Step 2: Decode and validate ────────────────────────────────────────
    try:
        payload = jwt.decode(refresh_token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please log in again.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type — expected a refresh token.",
        )

    user_id = payload["sub"]

    # Check if the user was globally revoked (e.g., after a detected theft)
    if r.get(f"revoked_user:{user_id}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked. Please log in again.",
        )

    # ── Step 3: Burn the old refresh token ────────────────────────────────
    # Store it in Redis with a 7-day TTL (same as its expiry).
    # After 7 days it would be expired anyway, so we don't need it longer.
    r.setex(f"burned:{refresh_token}", 7 * 24 * 3600, "revoked")

    # ── Step 4: Issue fresh tokens ─────────────────────────────────────────
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
    }


@app.get("/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """A protected route — requires a valid, non-expired access token.

    Pass the token in the Authorization header: Bearer <access_token>
    """
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired. Use /refresh to get a new one.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type — expected an access token.",
        )

    if r.get(f"revoked_user:{payload['sub']}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked. Please log in again.",
        )

    return {"user_id": payload["sub"], "message": "Access granted."}
