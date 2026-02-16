"""Tests for app/importer.py — CSV parsing, 3-pass import, DB import."""
import sqlite3
import tempfile
import os
import pytest
from app.importer import clean_name, parse_csv_rows, detect_and_resolve_duplicates, import_csv_text, import_db_file
from app import crud
from tests.conftest import SIMPLE_CSV, DUPLICATE_NAMES_CSV, SIBLING_CSV, SPOUSE_MERGE_CSV


# ── clean_name ──

class TestCleanName:
    def test_backslash_n(self):
        assert clean_name("John\\nSmith") == "John\nSmith"

    def test_whitespace(self):
        assert clean_name("  Alice  ") == "Alice"

    def test_both(self):
        assert clean_name("  Bob\\nJr  ") == "Bob\nJr"


# ── parse_csv_rows ──

class TestParseCsvRows:
    def test_basic(self):
        rows = parse_csv_rows(SIMPLE_CSV)
        assert len(rows) == 4
        assert rows[0]["raw_p1"] == "Grandpa"
        assert rows[0]["relation"] == "Earliest Ancestor"

    def test_skips_header(self):
        rows = parse_csv_rows(SIMPLE_CSV)
        # First row should NOT be the header
        assert rows[0]["raw_p1"] != "Person 1"

    def test_skips_comments(self):
        csv = "Person 1,Relation,Person 2,Gender,Details\n# Comment line\nJohn,Earliest Ancestor,,M,\n"
        rows = parse_csv_rows(csv)
        assert len(rows) == 1

    def test_skips_empty(self):
        csv = "Person 1,Relation,Person 2,Gender,Details\n\n\nJohn,Earliest Ancestor,,M,\n\n"
        rows = parse_csv_rows(csv)
        assert len(rows) == 1

    def test_nan_handling(self):
        csv = "Person 1,Relation,Person 2,Gender,Details\nJohn,Earliest Ancestor,,nan,nan\n"
        rows = parse_csv_rows(csv)
        assert rows[0]["gender"] == "U"
        assert rows[0]["details"] == ""


# ── detect_and_resolve_duplicates ──

class TestDetectDuplicates:
    def test_no_duplicates(self):
        rows = [
            {"line": 2, "raw_p1": "Alice", "relation": "Child", "raw_p2": "Mom", "gender": "F", "details": ""},
            {"line": 3, "raw_p1": "Bob", "relation": "Child", "raw_p2": "Mom", "gender": "M", "details": ""},
        ]
        rename_map, _, auto_fixes, _ = detect_and_resolve_duplicates(rows)
        assert len(rename_map) == 0

    def test_renames(self):
        rows = [
            {"line": 2, "raw_p1": "John", "relation": "Child", "raw_p2": "Alice", "gender": "M", "details": ""},
            {"line": 3, "raw_p1": "John", "relation": "Child", "raw_p2": "Bob", "gender": "M", "details": ""},
        ]
        rename_map, _, auto_fixes, _ = detect_and_resolve_duplicates(rows)
        assert len(rename_map) == 2
        assert ("John", "Alice") in rename_map
        assert ("John", "Bob") in rename_map

    def test_auto_fix_messages(self):
        rows = [
            {"line": 2, "raw_p1": "John", "relation": "Child", "raw_p2": "Alice", "gender": "M", "details": ""},
            {"line": 3, "raw_p1": "John", "relation": "Child", "raw_p2": "Bob", "gender": "M", "details": ""},
        ]
        _, _, auto_fixes, _ = detect_and_resolve_duplicates(rows)
        assert len(auto_fixes) == 2
        assert all(f["type"] == "auto_renamed" for f in auto_fixes)


# ── import_csv_text ──

class TestImportCsvText:
    def test_simple(self, conn, tree_one):
        result = import_csv_text(conn, SIMPLE_CSV, tree_id=tree_one["id"])
        assert result["people"] >= 4
        assert result["relationships"] >= 2

    def test_empty(self, conn, tree_one):
        result = import_csv_text(conn, "Person 1,Relation,Person 2,Gender,Details\n", tree_id=tree_one["id"])
        assert result["people"] == 0
        assert result["errors"][0]["type"] == "empty"

    def test_with_clear(self, conn, tree_one):
        crud.create_person(conn, "Existing", tree_id=tree_one["id"])
        result = import_csv_text(conn, SIMPLE_CSV, clear_first=True, tree_id=tree_one["id"])
        people = crud.list_people(conn, tree_id=tree_one["id"])
        names = [p["display_name"] for p in people]
        assert "Existing" not in names

    def test_duplicate_names(self, conn, tree_one):
        result = import_csv_text(conn, DUPLICATE_NAMES_CSV, tree_id=tree_one["id"])
        assert result["people"] >= 2
        # Should have auto_fixes for the duplicate "John"
        renamed = [f for f in result["auto_fixes"] if f["type"] == "auto_renamed"]
        assert len(renamed) >= 1

    def test_spouse_merges_children(self, conn, tree_one):
        result = import_csv_text(conn, SPOUSE_MERGE_CSV, tree_id=tree_one["id"])
        # ChildX should exist once, with both parents
        people = crud.list_people(conn, tree_id=tree_one["id"])
        child_xs = [p for p in people if "ChildX" in p["display_name"]]
        assert len(child_xs) >= 1

    def test_sibling_relation(self, conn, tree_one):
        result = import_csv_text(conn, SIBLING_CSV, tree_id=tree_one["id"])
        assert result["relationships"] >= 1
        # Child2 should share Parent1 as a parent
        child2 = crud.find_person_by_name(conn, "Child2", tree_id=tree_one["id"])
        if child2:
            parents = crud.get_parents(conn, child2["id"])
            parent_names = [p["display_name"] for p in parents]
            assert "Parent1" in parent_names

    def test_unknown_relation(self, conn, tree_one):
        csv = "Person 1,Relation,Person 2,Gender,Details\nJohn,FriendOf,Jane,M,\n"
        result = import_csv_text(conn, csv, tree_id=tree_one["id"])
        errors = [e for e in result["errors"] if e["type"] == "unknown_relation"]
        assert len(errors) == 1

    def test_duplicate_edge_dedup(self, conn, tree_one):
        csv = (
            "Person 1,Relation,Person 2,Gender,Details\n"
            "Parent,Earliest Ancestor,,M,\n"
            "Child,Child,Parent,M,\n"
            "Child,Child,Parent,M,\n"
        )
        result = import_csv_text(conn, csv, tree_id=tree_one["id"])
        skipped = [f for f in result["auto_fixes"] if f["type"] == "skip_duplicate_edge"]
        assert len(skipped) >= 1


# ── import_db_file ──

class TestImportDbFile:
    def _make_legacy_db(self):
        """Create a temp legacy SQLite DB with 'people' and 'relationships' tables."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        sdb = sqlite3.connect(path)
        sdb.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, raw_name TEXT, gender TEXT, details TEXT)")
        sdb.execute("CREATE TABLE relationships (person1_id INTEGER, relation TEXT, person2_id INTEGER)")
        sdb.execute("INSERT INTO people VALUES (1, 'Grandpa', 'M', 'patriarch')")
        sdb.execute("INSERT INTO people VALUES (2, 'Dad', 'M', NULL)")
        sdb.execute("INSERT INTO relationships VALUES (2, 'Child', 1)")
        sdb.commit()
        sdb.close()
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data

    def _make_starter_db(self):
        """Create a temp starter-schema SQLite DB with 'person' and 'relationship' tables."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        sdb = sqlite3.connect(path)
        sdb.execute("CREATE TABLE person (id INTEGER PRIMARY KEY, display_name TEXT, sex TEXT, notes TEXT)")
        sdb.execute("CREATE TABLE relationship (from_person_id INTEGER, to_person_id INTEGER, type TEXT)")
        sdb.execute("INSERT INTO person VALUES (1, 'Alice', 'F', 'note')")
        sdb.execute("INSERT INTO person VALUES (2, 'Bob', 'M', NULL)")
        sdb.execute("INSERT INTO relationship VALUES (1, 2, 'PARENT_OF')")
        sdb.commit()
        sdb.close()
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data

    def _make_unknown_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        sdb = sqlite3.connect(path)
        sdb.execute("CREATE TABLE unknown_table (id INTEGER)")
        sdb.commit()
        sdb.close()
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return data

    def test_legacy_schema(self, conn, tree_one):
        data = self._make_legacy_db()
        result = import_db_file(conn, data, tree_id=tree_one["id"])
        assert result["people"] >= 2
        assert result["relationships"] >= 1

    def test_starter_schema(self, conn, tree_one):
        data = self._make_starter_db()
        result = import_db_file(conn, data, tree_id=tree_one["id"])
        assert result["people"] >= 2
        assert result["relationships"] >= 1

    def test_unknown_schema(self, conn, tree_one):
        data = self._make_unknown_db()
        result = import_db_file(conn, data, tree_id=tree_one["id"])
        assert result["people"] == 0
        assert result["errors"][0]["type"] == "unknown_schema"
