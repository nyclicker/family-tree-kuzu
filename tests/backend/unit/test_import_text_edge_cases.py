"""
Unit tests for text importer edge cases and error handling.
"""

from app.importers.family_tree_text import (
    parse_family_tree_txt,
    build_people_set,
    build_relationship_requests,
    detect_duplicates,
)


def test_build_relationship_requests_unknown_relation_warns(tmp_path):
    content = """Person 1,Relation,Person 2,Gender,Details
Parent,Earliest Ancestor,,M,
Child,Sibling,Parent,F,
"""
    file_path = tmp_path / "unknown_relation.txt"
    file_path.write_text(content)

    rows = parse_family_tree_txt(file_path)
    people_dict = build_people_set(rows)
    name_map = {key: f"id_{i}" for i, key in enumerate(people_dict.keys())}

    rel_requests, warnings = build_relationship_requests(rows, name_map)

    assert rel_requests == []
    assert any("Skipped unknown relation" in w for w in warnings)


def test_build_relationship_requests_missing_person2_warns(tmp_path):
    content = """Person 1,Relation,Person 2,Gender,Details
Parent,Earliest Ancestor,,M,
Child,Child,,F,
"""
    file_path = tmp_path / "missing_parent.txt"
    file_path.write_text(content)

    rows = parse_family_tree_txt(file_path)
    people_dict = build_people_set(rows)
    name_map = {key: f"id_{i}" for i, key in enumerate(people_dict.keys())}

    rel_requests, warnings = build_relationship_requests(rows, name_map)

    assert rel_requests == []
    assert any("Person 2 is required" in w for w in warnings)


def test_build_relationship_requests_parent_after_child_warns(tmp_path):
    content = """Person 1,Relation,Person 2,Gender,Details
Child,Child,Parent,F,
Parent,Earliest Ancestor,,M,
"""
    file_path = tmp_path / "parent_after_child.txt"
    file_path.write_text(content)

    rows = parse_family_tree_txt(file_path)
    people_dict = build_people_set(rows)
    name_map = {key: f"id_{i}" for i, key in enumerate(people_dict.keys())}

    rel_requests, warnings = build_relationship_requests(rows, name_map)

    assert rel_requests == []
    assert any("not found before this line" in w for w in warnings)


def test_detect_duplicates_same_name_with_filename_prefix(tmp_path):
    content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,
John Doe,Child,John Doe,M,
"""
    file_path = tmp_path / "dups.txt"
    file_path.write_text(content)

    rows = parse_family_tree_txt(file_path)
    warnings = detect_duplicates(rows, filename=file_path.name)

    assert len(warnings) == 1
    assert "[dups.txt]" in warnings[0]
    assert "Duplicate person" in warnings[0]
