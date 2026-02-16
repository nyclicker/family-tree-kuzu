"""Tests for app/groups.py — group CRUD, membership."""
import pytest
from app import groups


# ── CRUD ──

class TestGroupCRUD:
    def test_create(self, conn, user_alice):
        g = groups.create_group(conn, "Test Group", "A description", user_alice["id"])
        assert g["name"] == "Test Group"
        assert g["description"] == "A description"
        assert g["created_by"] == user_alice["id"]

    def test_get_found(self, conn, user_alice):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        fetched = groups.get_group(conn, g["id"])
        assert fetched is not None
        assert fetched["name"] == "G"

    def test_get_not_found(self, conn):
        assert groups.get_group(conn, "nonexistent") is None

    def test_update(self, conn, user_alice):
        g = groups.create_group(conn, "Old Name", "Old desc", user_alice["id"])
        groups.update_group(conn, g["id"], "New Name", "New desc")
        fetched = groups.get_group(conn, g["id"])
        assert fetched["name"] == "New Name"
        assert fetched["description"] == "New desc"

    def test_delete_cascades(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        groups.delete_group(conn, g["id"])
        assert groups.get_group(conn, g["id"]) is None


# ── Membership ──

class TestMembership:
    def test_add_new(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        members = groups.list_members(conn, g["id"])
        assert len(members) == 1
        assert members[0]["id"] == user_bob["id"]

    def test_add_idempotent(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        members = groups.list_members(conn, g["id"])
        assert len(members) == 1

    def test_remove(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        groups.remove_member(conn, g["id"], user_bob["id"])
        members = groups.list_members(conn, g["id"])
        assert len(members) == 0

    def test_list_populated(self, conn, user_alice, user_bob, user_carol):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        groups.add_member(conn, g["id"], user_carol["id"])
        members = groups.list_members(conn, g["id"])
        assert len(members) == 2

    def test_list_empty(self, conn, user_alice):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        members = groups.list_members(conn, g["id"])
        assert members == []


# ── Listing ──

class TestGroupListing:
    def test_user_groups_created(self, conn, user_alice):
        groups.create_group(conn, "G1", "", user_alice["id"])
        result = groups.list_user_groups(conn, user_alice["id"])
        assert len(result) == 1

    def test_user_groups_member_of(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G1", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        result = groups.list_user_groups(conn, user_bob["id"])
        assert len(result) == 1
        assert result[0]["is_member"] is True

    def test_all_groups(self, conn, user_alice, user_bob):
        groups.create_group(conn, "G1", "", user_alice["id"])
        groups.create_group(conn, "G2", "", user_bob["id"])
        result = groups.list_all_groups(conn)
        assert len(result) == 2

    def test_group_trees_populated(self, conn, user_alice, tree_one):
        from app import trees as trees_mod
        g = groups.create_group(conn, "G", "", user_alice["id"])
        trees_mod.grant_group_access(conn, tree_one["id"], g["id"], "viewer")
        result = groups.list_group_trees(conn, g["id"])
        assert len(result) == 1
        assert result[0]["role"] == "viewer"

    def test_group_trees_empty(self, conn, user_alice):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        result = groups.list_group_trees(conn, g["id"])
        assert result == []


# ── Permission ──

class TestCanManageGroup:
    def test_creator(self, conn, user_alice):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        assert groups.can_manage_group(conn, g["id"], user_alice["id"], False) is True

    def test_admin(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        assert groups.can_manage_group(conn, g["id"], user_bob["id"], True) is True

    def test_non_creator(self, conn, user_alice, user_bob):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        assert groups.can_manage_group(conn, g["id"], user_bob["id"], False) is False
