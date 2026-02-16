"""Tests for app/changelog.py — record/list changes."""
import time
from app import changelog


def test_record_change(conn, tree_one, user_alice):
    result = changelog.record_change(
        conn, tree_one["id"], user_alice["id"], "Alice",
        "create", "person", "p1", "details here",
    )
    assert "id" in result
    assert "created_at" in result


def test_list_changes_empty(conn, tree_one):
    changes = changelog.list_changes(conn, tree_one["id"])
    assert changes == []


def test_list_changes_ordered(conn, tree_one, user_alice):
    changelog.record_change(conn, tree_one["id"], user_alice["id"], "Alice", "create", "person", "p1")
    time.sleep(0.01)  # Ensure distinct timestamps
    changelog.record_change(conn, tree_one["id"], user_alice["id"], "Alice", "update", "person", "p1")
    changes = changelog.list_changes(conn, tree_one["id"])
    assert len(changes) == 2
    # Newest first
    assert changes[0]["action"] == "update"
    assert changes[1]["action"] == "create"


def test_list_changes_limit(conn, tree_one, user_alice):
    for i in range(5):
        changelog.record_change(
            conn, tree_one["id"], user_alice["id"], "Alice",
            f"action_{i}", "person", f"p{i}",
        )
    changes = changelog.list_changes(conn, tree_one["id"], limit=2)
    assert len(changes) == 2


def test_list_changes_offset(conn, tree_one, user_alice):
    for i in range(5):
        changelog.record_change(
            conn, tree_one["id"], user_alice["id"], "Alice",
            f"action_{i}", "person", f"p{i}",
        )
    changes = changelog.list_changes(conn, tree_one["id"], limit=50, offset=3)
    assert len(changes) == 2
