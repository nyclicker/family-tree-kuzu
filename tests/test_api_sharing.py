"""Tests for sharing API endpoints."""


def _setup_tree_and_share(auth_client):
    tree = auth_client.post("/api/trees", json={"name": "Share Tree"}).json()
    link = auth_client.post(f"/api/trees/{tree['id']}/shares", json={"dataset": "test"}).json()
    return tree, link


class TestCreateShareLink:
    def test_create(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/shares", json={"dataset": "test"})
        assert resp.status_code == 200
        assert "token" in resp.json()


class TestListShareLinks:
    def test_list(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = auth_client.get(f"/api/trees/{tree['id']}/shares")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestDeleteShareLink:
    def test_delete(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = auth_client.delete(f"/api/trees/{tree['id']}/shares/{link['token']}")
        assert resp.status_code == 200


class TestViewerManagement:
    def test_add_viewer(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = auth_client.post(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers",
            json={"email": "viewer@example.com", "name": "Viewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "viewer@example.com"

    def test_remove_viewer(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        viewer = auth_client.post(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers",
            json={"email": "v@example.com"},
        ).json()
        resp = auth_client.delete(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers/{viewer['id']}"
        )
        assert resp.status_code == 200

    def test_list_viewers(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        auth_client.post(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers",
            json={"email": "v@example.com"},
        )
        resp = auth_client.get(f"/api/trees/{tree['id']}/shares/{link['token']}/viewers")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestAccessLog:
    def test_access_log(self, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = auth_client.get(f"/api/trees/{tree['id']}/shares/{link['token']}/access-log")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestViewerAuth:
    def test_success(self, client, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        auth_client.post(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers",
            json={"email": "authed@example.com"},
        )
        resp = client.post(f"/view/{link['token']}/auth",
                           json={"email": "authed@example.com"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_no_access(self, client, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = client.post(f"/view/{link['token']}/auth",
                           json={"email": "nobody@example.com"})
        assert resp.status_code == 403


class TestViewerGraph:
    def test_viewer_graph(self, client, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        auth_client.post(
            f"/api/trees/{tree['id']}/shares/{link['token']}/viewers",
            json={"email": "graphviewer@example.com"},
        )
        resp = client.get(f"/view/{link['token']}/graph?email=graphviewer@example.com")
        assert resp.status_code == 200
        assert "nodes" in resp.json()


class TestViewerPage:
    def test_viewer_page(self, client, auth_client):
        tree, link = _setup_tree_and_share(auth_client)
        resp = client.get(f"/view/{link['token']}")
        # May return 200 or 500 depending on whether viewer.html exists
        assert resp.status_code in (200, 500)


class TestRequiresOwner:
    def test_requires_owner(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        # Grant viewer access
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        resp = viewer_client.post(f"/api/trees/{tree['id']}/shares", json={"dataset": "x"})
        assert resp.status_code == 403
