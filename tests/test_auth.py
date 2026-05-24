"""Tests for authentication and security features."""

from __future__ import annotations

import hashlib
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(init_test_db):
    with TestClient(app) as c:
        yield c


def test_auth_disabled_by_default(monkeypatch, client):
    """When APP_PASSWORD and API_KEY are not set in env, all pages and APIs are open."""
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    
    # API check (should succeed/not return 401)
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    
    # Web check (should render dashboard, not redirect to login)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "dashboard" in resp.text.lower()


def test_api_auth_enabled_separate(monkeypatch, client):
    """When only API_KEY is set, API routes require it, but Web UI is open."""
    monkeypatch.setenv("API_KEY", "api-secret-token")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    
    # 1. API access without credentials -> 401
    resp = client.get("/api/portfolio")
    assert resp.status_code == 401
    
    # 2. API access with invalid key -> 401
    resp = client.get("/api/portfolio", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401
    
    # 3. API access with valid X-API-Key -> 200
    resp = client.get("/api/portfolio", headers={"X-API-Key": "api-secret-token"})
    assert resp.status_code == 200
    
    # 4. Web UI check -> should be accessible (since APP_PASSWORD is not set)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "dashboard" in resp.text.lower()


def test_web_auth_enabled_separate(monkeypatch, client):
    """When only APP_PASSWORD is set, Web UI requires login, but API is open."""
    monkeypatch.setenv("APP_PASSWORD", "web-pass-123")
    monkeypatch.delenv("API_KEY", raising=False)
    
    # 1. API access -> should be open (since API_KEY is not set)
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200
    
    # 2. Web GET / -> should redirect to /login
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_flow(monkeypatch, client):
    """Test full web login, cookie issuance, and logout flow."""
    monkeypatch.setenv("APP_PASSWORD", "web-pass-123")
    
    # 1. GET /login -> should be accessible
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Login" in resp.text
    
    # 2. POST /login with wrong password -> redirects back to login with error
    resp = client.post(
        "/login", 
        data={"password": "wrong_password"}, 
        headers={"Origin": "http://testserver"}, 
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert "/login?error=" in resp.headers["location"]
    
    # 3. POST /login with correct password -> redirects to / and sets cookie
    resp = client.post(
        "/login", 
        data={"password": "web-pass-123"}, 
        headers={"Origin": "http://testserver"}, 
        follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    
    # Verify cookie
    cookie = resp.cookies.get("set_chan_session")
    assert cookie is not None
    expected_hash = hashlib.sha256(b"web-pass-123").hexdigest()
    assert cookie == expected_hash
    
    # 4. Access protected page with valid cookie -> 200
    client.cookies.set("set_chan_session", expected_hash)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "dashboard" in resp.text.lower()
    
    # 5. GET /logout -> should delete cookie and redirect to /login
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
