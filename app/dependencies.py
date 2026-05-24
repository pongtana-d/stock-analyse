"""Shared dependencies (legacy helpers retained for backwards-compat).

Portfolio I/O has moved to ``app.repositories.portfolio_repo`` (SQLite).
"""

from __future__ import annotations

import hashlib
import os
from fastapi import Request, HTTPException, Depends, Header, status

class NeedLoginException(Exception):
    """Exception raised when a user is not logged in."""
    pass

def get_app_password() -> str | None:
    return os.getenv("APP_PASSWORD")

def get_api_key() -> str | None:
    return os.getenv("API_KEY")

async def verify_web_auth(request: Request):
    app_password = get_app_password()
    if not app_password:
        return

    session_cookie = request.cookies.get("set_chan_session")
    expected_hash = hashlib.sha256(app_password.encode()).hexdigest()
    if session_cookie != expected_hash:
        raise NeedLoginException()

async def verify_api_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
):
    api_key = get_api_key()
    if not api_key:
        return
    
    if x_api_key == api_key:
        return
        
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token == api_key:
            return
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing or invalid API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )
