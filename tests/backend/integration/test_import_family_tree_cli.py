"""
Integration tests for app.importers.import_family_tree CLI.
"""

import json
import sys

import pytest

from app.importers import import_family_tree
from app.main import app, get_db
from app.models import Person, Relationship


def _run_cli_with_db(monkeypatch, db_session, file_path):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(sys, "argv", ["import_family_tree.py", str(file_path)])
    try:
        import_family_tree.main()
    finally:
        app.dependency_overrides.clear()


def test_cli_import_text_file_creates_people_and_relationships(tmp_path, monkeypatch, db_session, capsys):
    content = """Person 1,Relation,Person 2,Gender,Details
Parent,Earliest Ancestor,,M,
Child,Child,Parent,F,
Parent,Earliest Ancestor,,M,Duplicate entry
"""
    file_path = tmp_path / "family.txt"
    file_path.write_text(content)

    _run_cli_with_db(monkeypatch, db_session, file_path)

    captured = capsys.readouterr().out
    assert "Import complete" in captured
    assert "DUPLICATE WARNINGS" in captured

    assert db_session.query(Person).count() >= 2
    assert db_session.query(Relationship).count() >= 1


def test_cli_import_json_file_creates_people(tmp_path, monkeypatch, db_session):
    payload = {
        "people": [
            {"id": "1", "display_name": "John", "sex": "M"},
            {"id": "2", "display_name": "Jane", "sex": "F"},
        ],
        "relationships": [],
    }
    file_path = tmp_path / "family.json"
    file_path.write_text(json.dumps(payload))

    _run_cli_with_db(monkeypatch, db_session, file_path)

    assert db_session.query(Person).count() >= 2


def test_cli_missing_file_exits(monkeypatch):
    missing_path = "/tmp/does_not_exist.txt"
    monkeypatch.setattr(sys, "argv", ["import_family_tree.py", missing_path])

    with pytest.raises(SystemExit) as exc:
        import_family_tree.main()

    assert "File not found" in str(exc.value)


def test_cli_unsupported_extension_exits(tmp_path, monkeypatch):
    file_path = tmp_path / "family.bin"
    file_path.write_bytes(b"binary")

    monkeypatch.setattr(sys, "argv", ["import_family_tree.py", str(file_path)])

    with pytest.raises(SystemExit) as exc:
        import_family_tree.main()

    assert "Unsupported file format" in str(exc.value)
