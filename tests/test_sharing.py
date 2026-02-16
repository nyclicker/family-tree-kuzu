"""Tests for app/sharing.py — share links, viewers, access log."""
from app import sharing


# ── Share links ──

class TestShareLinks:
    def test_create_basic(self, conn):
        link = sharing.create_share_link(conn, "my_dataset")
        assert link["token"]
        assert link["dataset"] == "my_dataset"

    def test_create_with_tree_id(self, conn, tree_one):
        link = sharing.create_share_link(conn, "ds", tree_id=tree_one["id"])
        assert link["tree_id"] == tree_one["id"]

    def test_list_all(self, conn):
        sharing.create_share_link(conn, "ds1")
        sharing.create_share_link(conn, "ds2")
        links = sharing.list_share_links(conn)
        assert len(links) == 2

    def test_list_by_tree_id(self, conn, tree_one, tree_two):
        sharing.create_share_link(conn, "ds1", tree_id=tree_one["id"])
        sharing.create_share_link(conn, "ds2", tree_id=tree_two["id"])
        links = sharing.list_share_links(conn, tree_id=tree_one["id"])
        assert len(links) == 1
        assert links[0]["tree_id"] == tree_one["id"]

    def test_get_found(self, conn):
        link = sharing.create_share_link(conn, "ds")
        fetched = sharing.get_share_link(conn, link["token"])
        assert fetched is not None
        assert fetched["dataset"] == "ds"

    def test_get_not_found(self, conn):
        assert sharing.get_share_link(conn, "nonexistent") is None

    def test_delete(self, conn):
        link = sharing.create_share_link(conn, "ds")
        sharing.delete_share_link(conn, link["token"])
        assert sharing.get_share_link(conn, link["token"]) is None


# ── Viewers ──

class TestViewers:
    def test_add_new(self, conn):
        link = sharing.create_share_link(conn, "ds")
        viewer = sharing.add_viewer(conn, link["token"], "viewer@example.com", "Viewer")
        assert viewer["email"] == "viewer@example.com"

    def test_add_idempotent(self, conn):
        link = sharing.create_share_link(conn, "ds")
        v1 = sharing.add_viewer(conn, link["token"], "viewer@example.com", "Viewer")
        v2 = sharing.add_viewer(conn, link["token"], "viewer@example.com", "Viewer")
        assert v1["id"] == v2["id"]

    def test_add_existing_viewer_new_link(self, conn):
        link1 = sharing.create_share_link(conn, "ds1")
        link2 = sharing.create_share_link(conn, "ds2")
        v1 = sharing.add_viewer(conn, link1["token"], "viewer@example.com", "Viewer")
        v2 = sharing.add_viewer(conn, link2["token"], "viewer@example.com", "Viewer")
        assert v1["id"] == v2["id"]
        # Viewer has access to both links
        assert sharing.check_viewer_access(conn, link1["token"], "viewer@example.com") is not None
        assert sharing.check_viewer_access(conn, link2["token"], "viewer@example.com") is not None

    def test_remove(self, conn):
        link = sharing.create_share_link(conn, "ds")
        viewer = sharing.add_viewer(conn, link["token"], "viewer@example.com")
        sharing.remove_viewer(conn, link["token"], viewer["id"])
        assert sharing.check_viewer_access(conn, link["token"], "viewer@example.com") is None

    def test_list(self, conn):
        link = sharing.create_share_link(conn, "ds")
        sharing.add_viewer(conn, link["token"], "a@example.com")
        sharing.add_viewer(conn, link["token"], "b@example.com")
        viewers = sharing.list_viewers(conn, link["token"])
        assert len(viewers) == 2

    def test_check_access_granted(self, conn):
        link = sharing.create_share_link(conn, "ds")
        sharing.add_viewer(conn, link["token"], "viewer@example.com")
        result = sharing.check_viewer_access(conn, link["token"], "viewer@example.com")
        assert result is not None
        assert result["email"] == "viewer@example.com"

    def test_check_access_denied(self, conn):
        link = sharing.create_share_link(conn, "ds")
        assert sharing.check_viewer_access(conn, link["token"], "nobody@example.com") is None


# ── Access log ──

class TestAccessLog:
    def test_log_access(self, conn):
        link = sharing.create_share_link(conn, "ds")
        viewer = sharing.add_viewer(conn, link["token"], "v@example.com")
        sharing.log_access(conn, link["token"], viewer["id"], "127.0.0.1")
        logs = sharing.get_access_log(conn, link["token"])
        assert len(logs) == 1
        assert logs[0]["email"] == "v@example.com"
        assert logs[0]["ip"] == "127.0.0.1"

    def test_get_access_log_empty(self, conn):
        link = sharing.create_share_link(conn, "ds")
        logs = sharing.get_access_log(conn, link["token"])
        assert logs == []
