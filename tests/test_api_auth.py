"""Tests for auth API endpoints."""
import os


class TestSetupStatus:
    def test_returns_needs_setup(self, client):
        resp = client.get("/api/auth/setup-status")
        assert resp.status_code == 200
        assert resp.json()["needs_setup"] is True


class TestRegister:
    def test_requires_setup_token(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "admin@test.com", "display_name": "Admin",
            "password": "password123",
        })
        assert resp.status_code == 403

    def test_wrong_token(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "admin@test.com", "display_name": "Admin",
            "password": "password123", "setup_token": "wrong-token",
        })
        assert resp.status_code == 403

    def test_success(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "admin@test.com", "display_name": "Admin",
            "password": "password123", "setup_token": os.environ["SETUP_TOKEN"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["is_admin"] is True

    def test_sets_cookie(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "cookie@test.com", "display_name": "Cookie",
            "password": "password123", "setup_token": os.environ["SETUP_TOKEN"],
        })
        assert "session" in resp.cookies

    def test_first_is_admin(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "first@test.com", "display_name": "First",
            "password": "password123", "setup_token": os.environ["SETUP_TOKEN"],
        })
        assert resp.json()["is_admin"] is True

    def test_duplicate(self, client):
        client.post("/api/auth/register", json={
            "email": "dup@test.com", "display_name": "Dup",
            "password": "password123", "setup_token": os.environ["SETUP_TOKEN"],
        })
        resp = client.post("/api/auth/register", json={
            "email": "dup@test.com", "display_name": "Dup2",
            "password": "password456",
        })
        assert resp.status_code == 400


class TestLogin:
    def _register(self, client):
        client.post("/api/auth/register", json={
            "email": "login@test.com", "display_name": "Login User",
            "password": "password123", "setup_token": os.environ["SETUP_TOKEN"],
        })

    def test_success(self, client):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@test.com", "password": "password123",
        })
        assert resp.status_code == 200
        assert resp.json()["email"] == "login@test.com"

    def test_wrong_password(self, client):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@test.com", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_nonexistent(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "whatever1",
        })
        assert resp.status_code == 401

    def test_sets_cookie(self, client):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@test.com", "password": "password123",
        })
        assert "session" in resp.cookies


class TestLogout:
    def test_logout(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestMe:
    def test_authenticated(self, auth_client):
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert "id" in resp.json()

    def test_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestMagicLogin:
    def test_valid(self, client, app_with_db, db):
        import kuzu
        from app import auth
        conn = kuzu.Connection(db)
        invited = auth.create_user_invited(conn, "magic@test.com", "Magic")
        resp = client.get(f"/auth/magic/{invited['magic_token']}", follow_redirects=False)
        assert resp.status_code == 302

    def test_invalid(self, client):
        resp = client.get("/auth/magic/invalid-token-xyz")
        assert resp.status_code == 404
