"""
Basic API smoke tests.
Run with: python3 -m pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

BASE = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    """Login once per session; reuse across all tests to avoid rate-limit on /token."""
    resp = client.post(
        f"{BASE}/auth/token",
        data={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Health & Root ────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "service" in r.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Auth ────────────────────────────────────────────────────────────────────

def test_login_success(client):
    r = client.post(f"{BASE}/auth/token", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post(f"{BASE}/auth/token", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_me(client, auth):
    r = client.get(f"{BASE}/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["is_admin"] is True


def test_me_no_auth(client):
    r = client.get(f"{BASE}/auth/me")
    assert r.status_code == 401


def test_create_and_delete_user(client, auth):
    r = client.post(
        f"{BASE}/auth/users",
        json={"username": "testuser", "password": "test123"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["username"] == "testuser"

    # Login as new user (separate call, counted against testuser's IP bucket)
    r2 = client.post(f"{BASE}/auth/token", data={"username": "testuser", "password": "test123"})
    assert r2.status_code == 200

    r = client.delete(f"{BASE}/auth/users/testuser", headers=auth)
    assert r.status_code == 200


def test_cannot_delete_self(client, auth):
    r = client.delete(f"{BASE}/auth/users/admin", headers=auth)
    assert r.status_code == 400


def test_list_users_requires_admin(client, auth):
    client.post(
        f"{BASE}/auth/users",
        json={"username": "nonadmin", "password": "pass123", "is_admin": False},
        headers=auth,
    )
    r2 = client.post(f"{BASE}/auth/token", data={"username": "nonadmin", "password": "pass123"})
    non_admin_token = r2.json()["access_token"]
    r = client.get(f"{BASE}/auth/users", headers={"Authorization": f"Bearer {non_admin_token}"})
    assert r.status_code == 403
    client.delete(f"{BASE}/auth/users/nonadmin", headers=auth)


# ── Instances ───────────────────────────────────────────────────────────────

def test_list_instances(client, auth):
    r = client.get(f"{BASE}/instances", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_nonexistent_instance(client, auth):
    r = client.get(f"{BASE}/instances/does-not-exist", headers=auth)
    assert r.status_code == 404


# ── Networks ────────────────────────────────────────────────────────────────

def test_list_networks(client, auth):
    r = client.get(f"{BASE}/networks", headers=auth)
    assert r.status_code == 200
    names = [n["name"] for n in r.json()]
    assert "lo" in names


def test_get_nonexistent_network(client, auth):
    r = client.get(f"{BASE}/networks/no-such-net", headers=auth)
    assert r.status_code == 404


# ── Profiles ────────────────────────────────────────────────────────────────

def test_list_profiles(client, auth):
    r = client.get(f"{BASE}/profiles", headers=auth)
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "default" in names


# ── Images ──────────────────────────────────────────────────────────────────

def test_list_images(client, auth):
    r = client.get(f"{BASE}/images", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Storage ──────────────────────────────────────────────────────────────────

def test_list_storage_pools(client, auth):
    r = client.get(f"{BASE}/storage/pools", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── System ──────────────────────────────────────────────────────────────────

def test_system_info(client, auth):
    r = client.get(f"{BASE}/system/info", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert "api_version" in data
    assert "resources" in data


# ── Rate Limiting ────────────────────────────────────────────────────────────

def test_rate_limit_login(client):
    """Login endpoint is limited to 10/minute — keep hammering until we get 429."""
    hit_429 = False
    for i in range(20):  # more than enough to exceed the 10/min limit
        r = client.post(
            f"{BASE}/auth/token",
            data={"username": "ratelimituser", "password": "wrong"},
        )
        if r.status_code == 429:
            hit_429 = True
            break
        assert r.status_code in (200, 401), f"unexpected {r.status_code} on attempt {i+1}"
    assert hit_429, "Expected a 429 after exceeding login rate limit"


def test_rate_limit_returns_retry_after(client):
    """A 429 response should include a Retry-After header."""
    for _ in range(20):
        r = client.post(
            f"{BASE}/auth/token",
            data={"username": "ratelimituser2", "password": "x"},
        )
        if r.status_code == 429:
            assert "retry-after" in r.headers
            return
    pytest.skip("Rate limit was not triggered within 20 requests")
