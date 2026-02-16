"""Tests for admin API endpoints."""


class TestListUsers:
    def test_admin(self, auth_client):
        resp = auth_client.get("/api/admin/users")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_non_admin(self, viewer_client):
        resp = viewer_client.get("/api/admin/users")
        assert resp.status_code == 403


class TestCreateUser:
    def test_normal(self, auth_client):
        resp = auth_client.post("/api/admin/users", json={
            "email": "newadmin@test.com", "display_name": "New Admin",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newadmin@test.com"
        assert "magic_link" in data

    def test_duplicate(self, auth_client):
        auth_client.post("/api/admin/users", json={
            "email": "dup@admin.com", "display_name": "Dup",
        })
        resp = auth_client.post("/api/admin/users", json={
            "email": "dup@admin.com", "display_name": "Dup2",
        })
        assert resp.status_code == 400


class TestUpdateUser:
    def test_normal(self, auth_client):
        created = auth_client.post("/api/admin/users", json={
            "email": "updateme@test.com", "display_name": "Old Name",
        }).json()
        resp = auth_client.put(f"/api/admin/users/{created['id']}",
                               json={"display_name": "New Name"})
        assert resp.status_code == 200

    def test_not_found(self, auth_client):
        resp = auth_client.put("/api/admin/users/nonexistent",
                               json={"display_name": "X"})
        assert resp.status_code == 404


class TestGetMagicLink:
    def test_normal(self, auth_client):
        created = auth_client.post("/api/admin/users", json={
            "email": "magicadmin@test.com", "display_name": "Magic",
        }).json()
        resp = auth_client.get(f"/api/admin/users/{created['id']}/magic-link")
        assert resp.status_code == 200
        assert "magic_link" in resp.json()

    def test_not_found(self, auth_client):
        resp = auth_client.get("/api/admin/users/nonexistent/magic-link")
        assert resp.status_code == 404


class TestListAllTrees:
    def test_admin(self, auth_client):
        auth_client.post("/api/trees", json={"name": "Admin Tree"})
        resp = auth_client.get("/api/admin/trees")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_non_admin(self, viewer_client):
        resp = viewer_client.get("/api/admin/trees")
        assert resp.status_code == 403
