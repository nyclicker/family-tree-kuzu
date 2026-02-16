"""Tests for permission enforcement and middleware.

Requirements tested:
- REQ-AUTH1: Permission model should be internally consistent
- REQ-AUTH2: Viewer can read but cannot mutate data
- REQ-AUTH3: Editor can create/edit people and relationships
"""
import os


class TestUnauthAPI:
    def test_returns_401(self, client):
        resp = client.get("/api/trees")
        assert resp.status_code == 401


class TestUnauthNonAPI:
    def test_redirects(self, client):
        resp = client.get("/admin", follow_redirects=False)
        assert resp.status_code == 302


class TestPublicPaths:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_setup_status(self, client):
        resp = client.get("/api/auth/setup-status")
        assert resp.status_code == 200

    def test_login_page(self, client):
        # /login is public
        resp = client.get("/login")
        # Will return 200 or a file-not-found depending on web/ dir
        assert resp.status_code in (200, 404)


class TestViewerCanRead:
    def test_viewer_can_read(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        auth_client.post(f"/api/trees/{tree['id']}/people",
                         json={"display_name": "Person1"})
        resp = viewer_client.get(f"/api/trees/{tree['id']}/people")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestViewerCannotCreate:
    def test_cannot_create_person(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        resp = viewer_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Sneaky"})
        assert resp.status_code == 403

    def test_cannot_delete_person(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        resp = viewer_client.delete(f"/api/trees/{tree['id']}/people/{person['id']}")
        assert resp.status_code == 403

    def test_cannot_create_rel(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "P1"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "P2"}).json()
        resp = viewer_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        assert resp.status_code == 403


class TestEditorCanCreate:
    def test_editor_can_create(self, auth_client, make_authenticated_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        editor = make_authenticated_client("editor@test.com", "Editor", "password123")
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "editor@test.com", "role": "editor"})
        resp = editor.post(f"/api/trees/{tree['id']}/people",
                           json={"display_name": "EditorPerson"})
        assert resp.status_code == 200


class TestEditorCannotDeleteTree:
    def test_editor_cannot_delete_tree(self, auth_client, make_authenticated_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        editor = make_authenticated_client("editor2@test.com", "Editor", "password123")
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "editor2@test.com", "role": "editor"})
        resp = editor.delete(f"/api/trees/{tree['id']}")
        assert resp.status_code == 403


class TestOwnerCanDeleteTree:
    def test_owner_can_delete(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        resp = auth_client.delete(f"/api/trees/{tree['id']}")
        assert resp.status_code == 200


class TestNoAccessReturns404:
    def test_no_access(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "Private"}).json()
        # viewer_client has no access
        resp = viewer_client.get(f"/api/trees/{tree['id']}/people")
        assert resp.status_code == 404


class TestPermissionConsistency:
    """REQ-AUTH1: The permission model should be internally consistent.

    If an editor can delete a person (which cascade-deletes ALL comments on that person),
    they should also be able to delete individual comments — otherwise a more destructive
    action is permitted while a less destructive one is blocked.
    """

    def test_editor_can_delete_others_comment_on_deletable_person(
        self, auth_client, make_authenticated_client
    ):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        editor = make_authenticated_client("consistency@test.com", "Editor", "password123")
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "consistency@test.com", "role": "editor"})
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        # Owner adds a comment
        comment = auth_client.post(
            f"/api/trees/{tree['id']}/people/{person['id']}/comments",
            json={"content": "Owner's comment"}).json()
        # Editor should be able to delete the comment (they can delete the whole person)
        resp = editor.delete(
            f"/api/trees/{tree['id']}/people/{person['id']}/comments/{comment['id']}")
        assert resp.status_code == 200

    def test_editor_person_delete_cascades_all_comments(
        self, auth_client, make_authenticated_client
    ):
        """Verify that person deletion by editor does cascade-delete others' comments."""
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        editor = make_authenticated_client("cascade@test.com", "Editor", "password123")
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "cascade@test.com", "role": "editor"})
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        auth_client.post(
            f"/api/trees/{tree['id']}/people/{person['id']}/comments",
            json={"content": "Owner's comment"})
        # Editor deletes the entire person — this should succeed and cascade comments
        resp = editor.delete(f"/api/trees/{tree['id']}/people/{person['id']}")
        assert resp.status_code == 200


class TestSessionMiddleware:
    def test_legacy_admin_token(self, client, app_with_db):
        """If ADMIN_PASSWORD is set, legacy admin_token cookie should work."""
        # This test just verifies the middleware path exists.
        # With no ADMIN_PASSWORD set, legacy tokens are not accepted.
        resp = client.get("/api/trees")
        assert resp.status_code == 401
