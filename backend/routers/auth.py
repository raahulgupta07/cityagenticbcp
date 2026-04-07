"""Auth router — login, JWT, current user."""
from __future__ import annotations
import os
import hashlib
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from utils.database import get_db

router = APIRouter()
security = HTTPBearer()

SECRET_KEY = os.environ.get("JWT_SECRET", "").strip()
if not SECRET_KEY:
    # Auto-generate and persist to db volume so it survives restarts
    import secrets
    from pathlib import Path
    _secret_file = Path(os.environ.get("DATA_DIR", "db")) / ".jwt_secret"
    _secret_file.parent.mkdir(parents=True, exist_ok=True)
    if _secret_file.exists():
        SECRET_KEY = _secret_file.read_text().strip()
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(32)
        _secret_file.write_text(SECRET_KEY)
        print(f"[AUTH] Auto-generated JWT_SECRET → saved to {_secret_file}")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


# ─── Models ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    role: str


# ─── Helpers ─────────────────────────────────────────────
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _create_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "username": username, "role": role, "exp": expire},
                      SECRET_KEY, algorithm=ALGORITHM)


def _validate_user(username: str, password: str) -> dict | None:
    """Check DB users table + super admin env."""
    # Check super admin from env
    sa_user = os.environ.get("SUPER_ADMIN_USER", "admin")
    sa_pass = os.environ.get("SUPER_ADMIN_PASS", "admin123")
    if username == sa_user and password == sa_pass:
        return {"id": 0, "username": sa_user, "display_name": "Super Admin",
                "email": os.environ.get("SUPER_ADMIN_EMAIL", ""), "role": "super_admin"}

    # Check DB
    pw_hash = _hash(password)
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, display_name, email, role FROM users WHERE username = ? AND password_hash = ? AND is_active = 1",
            (username, pw_hash)
        ).fetchone()
    if row:
        return {"id": row[0], "username": row[1], "display_name": row[2], "email": row[3], "role": row[4]}
    return None


# ─── Dependency: get current user from JWT ───────────────
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": int(user_id), "username": payload["username"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")


# ─── Role guards ─────────────────────────────────────────
async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ─── Endpoints ───────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = _validate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = _create_token(user["id"], user["username"], user["role"])
    return TokenResponse(access_token=token, user=user)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
