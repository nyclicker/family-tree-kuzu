"""Authentication: password hashing, session tokens, and FastAPI dependencies."""
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timezone

import bcrypt as _bcrypt
import kuzu
from fastapi import Depends, HTTPException, Request

from .db import get_conn

COOKIE_SECRET = os.environ.get("COOKIE_SECRET", "")
SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "")
SESSION_COOKIE = "session"


# ── Password hashing ──

def validate_password(password: str):
    """Validate password meets minimum requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password is too long (max 72 bytes)")


def hash_password(password: str) -> str:
    validate_password(password)
    pw_bytes = password.encode("utf-8")
    return _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── Session tokens ──

def create_session_token(user_id: str) -> str:
    """Create an HMAC-signed session token: user_id:timestamp:signature."""
    ts = str(int(time.time()))
    payload = f"{user_id}:{ts}"
    sig = hmac.new(COOKIE_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str) -> str | None:
    """Verify session token. Returns user_id if valid, None otherwise."""
    if not token or not COOKIE_SECRET:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id, ts, sig = parts
    payload = f"{user_id}:{ts}"
    expected = hmac.new(COOKIE_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return user_id


# ── User CRUD ──

def create_user(conn: kuzu.Connection, email: str, display_name: str,
                password: str, is_admin: bool = False) -> dict:
    """Create a new user account."""
    email = email.strip().lower()
    # Check for duplicate email
    existing = get_user_by_email(conn, email)
    if existing:
        raise ValueError("A user with this email already exists")
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    conn.execute(
        "CREATE (u:User {id: $id, email: $email, display_name: $name, "
        "password_hash: $hash, is_admin: $admin, created_at: $ts})",
        {"id": uid, "email": email, "name": display_name,
         "hash": pw_hash, "admin": is_admin, "ts": now}
    )
    return {"id": uid, "email": email, "display_name": display_name,
            "is_admin": is_admin, "created_at": now}


def get_user_by_email(conn: kuzu.Connection, email: str) -> dict | None:
    email = email.strip().lower()
    result = conn.execute(
        "MATCH (u:User) WHERE u.email = $email "
        "RETURN u.id, u.email, u.display_name, u.password_hash, u.is_admin, u.created_at",
        {"email": email}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "email": row[1], "display_name": row[2],
                "password_hash": row[3], "is_admin": row[4], "created_at": row[5]}
    return None


def get_user_by_id(conn: kuzu.Connection, user_id: str) -> dict | None:
    result = conn.execute(
        "MATCH (u:User) WHERE u.id = $id "
        "RETURN u.id, u.email, u.display_name, u.password_hash, u.is_admin, u.created_at",
        {"id": user_id}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "email": row[1], "display_name": row[2],
                "password_hash": row[3], "is_admin": row[4], "created_at": row[5]}
    return None


def count_users(conn: kuzu.Connection) -> int:
    result = conn.execute("MATCH (u:User) RETURN count(*)")
    if result.has_next():
        return result.get_next()[0]
    return 0


def authenticate_user(conn: kuzu.Connection, email: str, password: str) -> dict | None:
    """Verify email+password. Returns user dict (without password_hash) or None."""
    user = get_user_by_email(conn, email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}


# ── FastAPI dependencies ──

def get_current_user(request: Request, conn=Depends(get_conn)) -> dict:
    """FastAPI dependency: extract user from session cookie. Raises 401 if not authenticated."""
    token = request.cookies.get(SESSION_COOKIE)
    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    user = get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return {k: v for k, v in user.items() if k != "password_hash"}


def get_optional_user(request: Request, conn=Depends(get_conn)) -> dict | None:
    """FastAPI dependency: extract user from session cookie. Returns None if not authenticated."""
    token = request.cookies.get(SESSION_COOKIE)
    user_id = verify_session_token(token)
    if not user_id:
        return None
    user = get_user_by_id(conn, user_id)
    if not user:
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}
