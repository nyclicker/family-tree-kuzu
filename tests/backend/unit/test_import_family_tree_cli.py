import sys

import pytest

from app.importers import import_family_tree


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class FakeClient:
    def __init__(self, app):
        self.app = app
        self.post_calls = []
        self.people_counter = 0

    def post(self, path, json=None):
        self.post_calls.append((path, json))
        if path == "/trees/import":
            return FakeResponse(200, {"tree_id": 1, "tree_version_id": 1, "version": 1})
        if path == "/people":
            self.people_counter += 1
            return FakeResponse(200, {"id": str(self.people_counter)})
        if path == "/relationships":
            return FakeResponse(200, {"id": "rel-1"})
        return FakeResponse(404, text="not found")


def _run_main(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["import_family_tree.py", *args])
    import_family_tree.main()


def test_main_missing_file_raises_system_exit(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing.txt"
    monkeypatch.setattr(import_family_tree, "TestClient", FakeClient)

    with pytest.raises(SystemExit) as excinfo:
        _run_main(monkeypatch, [str(missing_file)])

    assert "File not found" in str(excinfo.value)


def test_main_unsupported_extension_raises_system_exit(monkeypatch, tmp_path):
    unsupported = tmp_path / "data.bin"
    unsupported.write_bytes(b"binary")
    monkeypatch.setattr(import_family_tree, "TestClient", FakeClient)

    with pytest.raises(SystemExit) as excinfo:
        _run_main(monkeypatch, [str(unsupported)])

    assert "Unsupported file format" in str(excinfo.value)


def test_main_text_import_prints_duplicate_and_relationship_warnings(monkeypatch, tmp_path, capsys):
    content = (
        "Person 1,Relation,Person 2,Gender,Details\n"
        "Alex Doe,Earliest Ancestor,,M,\n"
        "Alex Doe,Earliest Ancestor,,M,\n"
        "Sam Doe,Child,Alex Doe,F,\n"
        "Chris Doe,Unknown,Alex Doe,M,\n"
    )
    text_file = tmp_path / "family.txt"
    text_file.write_text(content, encoding="utf-8")

    fake_client = FakeClient
    monkeypatch.setattr(import_family_tree, "TestClient", fake_client)

    _run_main(monkeypatch, [str(text_file)])
    output = capsys.readouterr().out

    assert "DUPLICATE WARNINGS" in output
    assert "RELATIONSHIP WARNINGS" in output
    assert "Import complete" in output


def test_main_json_import_creates_people(monkeypatch, tmp_path):
    json_file = tmp_path / "tree.json"
    json_file.write_text(
        '{"people": [{"id": "1", "display_name": "John", "sex": "M"}], "relationships": []}',
        encoding="utf-8",
    )

    fake_client = FakeClient
    monkeypatch.setattr(import_family_tree, "TestClient", fake_client)

    _run_main(monkeypatch, [str(json_file)])