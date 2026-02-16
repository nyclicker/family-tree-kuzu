"""Tests for group management API endpoints."""


class TestCreateGroup:
    def test_create(self, auth_client):
        resp = auth_client.post("/api/groups",
                                json={"name": "Test Group", "description": "Desc"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Group"


class TestListGroups:
    def test_admin(self, auth_client):
        auth_client.post("/api/groups", json={"name": "G1"})
        resp = auth_client.get("/api/groups")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_non_admin(self, auth_client, viewer_client):
        auth_client.post("/api/groups", json={"name": "Admin Group"})
        resp = viewer_client.get("/api/groups")
        assert resp.status_code == 200
        # Non-admin only sees their own groups
        assert isinstance(resp.json(), list)


class TestUpdateGroup:
    def test_owner(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "Old"}).json()
        resp = auth_client.put(f"/api/groups/{group['id']}",
                               json={"name": "New", "description": "Updated"})
        assert resp.status_code == 200

    def test_not_authorized(self, auth_client, viewer_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        resp = viewer_client.put(f"/api/groups/{group['id']}",
                                 json={"name": "Hack", "description": ""})
        assert resp.status_code == 403


class TestDeleteGroup:
    def test_delete(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "Delete Me"}).json()
        resp = auth_client.delete(f"/api/groups/{group['id']}")
        assert resp.status_code == 200


class TestListMembers:
    def test_list(self, auth_client, make_authenticated_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        bob = make_authenticated_client("bob3@test.com", "Bob", "password123")
        auth_client.post(f"/api/groups/{group['id']}/members",
                         json={"email": "bob3@test.com"})
        resp = auth_client.get(f"/api/groups/{group['id']}/members")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestAddMember:
    def test_existing_user(self, auth_client, make_authenticated_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        bob = make_authenticated_client("member@test.com", "Member", "password123")
        resp = auth_client.post(f"/api/groups/{group['id']}/members",
                                json={"email": "member@test.com"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_auto_creates_user(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        resp = auth_client.post(f"/api/groups/{group['id']}/members",
                                json={"email": "newmember@test.com"})
        assert resp.status_code == 200
        assert resp.json()["created"] is True

    def test_returns_magic_link(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        resp = auth_client.post(f"/api/groups/{group['id']}/members",
                                json={"email": "magicmember@test.com"})
        assert resp.status_code == 200
        assert "magic_link" in resp.json()


class TestRemoveMember:
    def test_remove(self, auth_client, make_authenticated_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        bob = make_authenticated_client("removeme@test.com", "Bob", "password123")
        auth_client.post(f"/api/groups/{group['id']}/members",
                         json={"email": "removeme@test.com"})
        resp = auth_client.delete(f"/api/groups/{group['id']}/members/{bob._test_user['id']}")
        assert resp.status_code == 200


class TestListGroupTrees:
    def test_list(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        resp = auth_client.get(f"/api/groups/{group['id']}/trees")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAssignTree:
    def test_assign(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        resp = auth_client.post(f"/api/groups/{group['id']}/trees",
                                json={"tree_id": tree["id"], "role": "editor"})
        assert resp.status_code == 200


class TestUpdateTreeRole:
    def test_update(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/groups/{group['id']}/trees",
                         json={"tree_id": tree["id"], "role": "viewer"})
        resp = auth_client.put(f"/api/groups/{group['id']}/trees/{tree['id']}",
                               json={"role": "editor"})
        assert resp.status_code == 200


class TestRemoveTree:
    def test_remove(self, auth_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/groups/{group['id']}/trees",
                         json={"tree_id": tree["id"], "role": "viewer"})
        resp = auth_client.delete(f"/api/groups/{group['id']}/trees/{tree['id']}")
        assert resp.status_code == 200


class TestRequiresManager:
    def test_requires_manager(self, auth_client, viewer_client):
        group = auth_client.post("/api/groups", json={"name": "G"}).json()
        resp = viewer_client.delete(f"/api/groups/{group['id']}")
        assert resp.status_code == 403
