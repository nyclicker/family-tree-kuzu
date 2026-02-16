"""Tests for app/trees.py — tree CRUD, permissions, role resolution.

Requirements tested:
- REQ-T1: Deleting a tree removes ALL associated data (people, comments, share links, changelog)
- REQ-T2: Tree isolation — operations on one tree never affect another
- REQ-T3: Role hierarchy is enforced: owner > editor > viewer > none
- REQ-T4: Users only see trees they have access to (owned, direct, group)
"""
import pytest
from fastapi import HTTPException
from app import trees, groups, crud, sharing, changelog


# ── CRUD ──

class TestTreeCRUD:
    def test_create(self, conn, user_alice):
        t = trees.create_tree(conn, "My Tree", user_alice["id"])
        assert t["name"] == "My Tree"
        assert t["role"] == "owner"

    def test_get_found(self, conn, tree_one):
        t = trees.get_tree(conn, tree_one["id"])
        assert t is not None
        assert t["name"] == "Tree One"

    def test_get_not_found(self, conn):
        assert trees.get_tree(conn, "nonexistent") is None

    def test_rename(self, conn, tree_one):
        trees.rename_tree(conn, tree_one["id"], "Renamed")
        t = trees.get_tree(conn, tree_one["id"])
        assert t["name"] == "Renamed"

    def test_delete_cascades(self, conn, tree_one, user_alice, person_grandpa):
        # Add a comment and share link
        crud.create_comment(
            conn, person_grandpa["id"], tree_one["id"],
            user_alice["id"], "Alice", "comment",
        )
        sharing.create_share_link(conn, "ds", tree_id=tree_one["id"])
        trees.delete_tree(conn, tree_one["id"])
        assert trees.get_tree(conn, tree_one["id"]) is None
        assert crud.list_people(conn, tree_id=tree_one["id"]) == []

    def test_delete_cascades_changelog(self, conn, tree_one, user_alice):
        """REQ-T1: Deleting a tree must also remove its changelog entries."""
        changelog.record_change(
            conn, tree_one["id"], user_alice["id"], "Alice",
            "create", "person", "p1", "details",
        )
        # Verify changelog exists before deletion
        changes_before = changelog.list_changes(conn, tree_one["id"])
        assert len(changes_before) >= 1
        trees.delete_tree(conn, tree_one["id"])
        # Changelog entries for deleted tree should be gone (no orphaned data)
        changes_after = changelog.list_changes(conn, tree_one["id"])
        assert changes_after == []

    def test_delete_tree_isolates_other_tree(self, conn, tree_one, tree_two, user_alice, user_bob):
        """REQ-T2: Deleting one tree must not affect another tree's data."""
        crud.create_person(conn, "T1Person", tree_id=tree_one["id"])
        crud.create_person(conn, "T2Person", tree_id=tree_two["id"])
        changelog.record_change(
            conn, tree_two["id"], user_bob["id"], "Bob",
            "create", "person", "p2",
        )
        trees.delete_tree(conn, tree_one["id"])
        # Tree two should be completely unaffected
        t2_people = crud.list_people(conn, tree_id=tree_two["id"])
        assert len(t2_people) == 1
        assert t2_people[0]["display_name"] == "T2Person"
        t2_changes = changelog.list_changes(conn, tree_two["id"])
        assert len(t2_changes) == 1


# ── list_user_trees ──

class TestListUserTrees:
    def test_owned(self, conn, user_alice, tree_one):
        result = trees.list_user_trees(conn, user_alice["id"])
        assert len(result) == 1
        assert result[0]["role"] == "owner"

    def test_direct_access(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        result = trees.list_user_trees(conn, user_bob["id"])
        assert any(t["id"] == tree_one["id"] and t["role"] == "viewer" for t in result)

    def test_group_access(self, conn, user_alice, user_bob, tree_one):
        g = groups.create_group(conn, "Test Group", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "editor")
        result = trees.list_user_trees(conn, user_bob["id"])
        assert any(t["id"] == tree_one["id"] and t["role"] == "editor" for t in result)

    def test_highest_role_wins(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "editor")
        result = trees.list_user_trees(conn, user_bob["id"])
        t = [t for t in result if t["id"] == tree_one["id"]][0]
        assert t["role"] == "editor"

    def test_sorted(self, conn, user_alice):
        trees.create_tree(conn, "Zeta Tree", user_alice["id"])
        trees.create_tree(conn, "Alpha Tree", user_alice["id"])
        result = trees.list_user_trees(conn, user_alice["id"])
        names = [t["name"] for t in result]
        assert names == sorted(names)


# ── get_user_role ──

class TestGetUserRole:
    def test_owner(self, conn, user_alice, tree_one):
        assert trees.get_user_role(conn, user_alice["id"], tree_one["id"]) == "owner"

    def test_direct_editor(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "editor")
        assert trees.get_user_role(conn, user_bob["id"], tree_one["id"]) == "editor"

    def test_direct_viewer(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        assert trees.get_user_role(conn, user_bob["id"], tree_one["id"]) == "viewer"

    def test_group_editor(self, conn, user_alice, user_bob, tree_one):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "editor")
        assert trees.get_user_role(conn, user_bob["id"], tree_one["id"]) == "editor"

    def test_none(self, conn, user_bob, tree_one):
        assert trees.get_user_role(conn, user_bob["id"], tree_one["id"]) == "none"

    def test_best_of_direct_and_group(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "editor")
        assert trees.get_user_role(conn, user_bob["id"], tree_one["id"]) == "editor"


# ── require_role ──

class TestRequireRole:
    def test_sufficient(self, conn, user_alice, tree_one):
        role = trees.require_role(conn, user_alice["id"], tree_one["id"], "viewer")
        assert role == "owner"

    def test_insufficient(self, conn, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        with pytest.raises(HTTPException) as exc_info:
            trees.require_role(conn, user_bob["id"], tree_one["id"], "owner")
        assert exc_info.value.status_code == 403

    def test_no_access(self, conn, user_bob, tree_one):
        with pytest.raises(HTTPException) as exc_info:
            trees.require_role(conn, user_bob["id"], tree_one["id"], "viewer")
        assert exc_info.value.status_code == 404


# ── Members ──

class TestTreeMembers:
    def test_grant_new(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "editor")
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "editor"

    def test_grant_update_existing(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "editor")
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "editor"

    def test_update(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        trees.update_user_access(conn, tree_one["id"], user_bob["id"], "editor")
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "editor"

    def test_revoke(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "editor")
        trees.revoke_user_access(conn, tree_one["id"], user_bob["id"])
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "none"

    def test_list(self, conn, user_alice, user_bob, tree_one):
        trees.grant_user_access(conn, tree_one["id"], user_bob["id"], "viewer")
        members = trees.list_tree_members(conn, tree_one["id"])
        assert members["owner"]["id"] == user_alice["id"]
        assert len(members["users"]) == 1
        assert members["users"][0]["id"] == user_bob["id"]


# ── Groups ──

class TestTreeGroupAccess:
    def test_grant(self, conn, user_alice, user_bob, tree_one):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "viewer")
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "viewer"

    def test_update(self, conn, user_alice, user_bob, tree_one):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "viewer")
        trees.update_group_access(conn, tree_one["id"], g["id"], "editor")
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "editor"

    def test_revoke(self, conn, user_alice, user_bob, tree_one):
        g = groups.create_group(conn, "G", "", user_alice["id"])
        groups.add_member(conn, g["id"], user_bob["id"])
        trees.grant_group_access(conn, tree_one["id"], g["id"], "viewer")
        trees.revoke_group_access(conn, tree_one["id"], g["id"])
        role = trees.get_user_role(conn, user_bob["id"], tree_one["id"])
        assert role == "none"


# ── Helper ──

class TestGetTreeOwnerId:
    def test_returns_owner(self, conn, user_alice, tree_one):
        assert trees.get_tree_owner_id(conn, tree_one["id"]) == user_alice["id"]

    def test_returns_none(self, conn):
        assert trees.get_tree_owner_id(conn, "nonexistent") is None
