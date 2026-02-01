"""
Integration tests for import workflow (text and JSON formats).

Tests the complete import pipeline including:
- File parsing (text/JSON)
- Person creation
- Relationship creation
- Duplicate detection
- Name normalization
- Tree versioning
"""

import pytest
import tempfile
import json
from pathlib import Path
from sqlalchemy.orm import Session

from app.importers.family_tree_text import (
    parse_family_tree_txt,
    build_people_set,
    build_relationship_requests,
    detect_duplicates,
    _parse_name_parts,
)
from app.importers.family_tree_json import (
    parse_family_tree_json,
    extract_people_for_import,
    extract_relationships_for_import,
)
from app.models import Person, Relationship, Tree, TreeVersion, RelType


class TestTextFileImport:
    """Test text file import pipeline."""

    def test_parse_simple_text_file(self, tmp_path):
        """Test parsing a simple text file."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,Patriarch
Jane Smith,,,F,Wife
Jack Doe,Child,John Doe,M,Son
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        
        assert len(rows) == 3
        assert rows[0].person1 == "John Doe"
        assert rows[0].relation == "Earliest Ancestor"
        assert rows[0].gender1 == "M"
        
        assert rows[1].person1 == "Jane Smith"
        assert rows[1].gender1 == "F"
        
        assert rows[2].person1 == "Jack Doe"
        assert rows[2].relation == "Child"
        assert rows[2].person2 == "John Doe"

    def test_parse_text_file_with_comments(self, tmp_path):
        """Test that comment lines are skipped."""
        content = """# This is a comment
Person 1,Relation,Person 2,Gender,Details
# Another comment
John Doe,Earliest Ancestor,,M,
Jane Smith,,,,F,
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        
        assert len(rows) == 2
        assert rows[0].person1 == "John Doe"
        assert rows[1].person1 == "Jane Smith"

    def test_parse_text_file_missing_columns(self, tmp_path):
        """Test handling of rows with missing trailing columns."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor
Jane Smith
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        
        assert len(rows) == 2
        assert rows[0].person1 == "John Doe"
        assert rows[0].gender1 == ""
        assert rows[1].person1 == "Jane Smith"

    def test_parse_text_file_not_found(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_family_tree_txt("/nonexistent/file.txt")


class TestNameParsing:
    """Test name parsing and normalization."""

    def test_parse_simple_name(self):
        """Test parsing a single name."""
        first, last, key = _parse_name_parts("John")
        assert first == "John"
        assert last == ""
        assert key == "John"

    def test_parse_first_last_name(self):
        """Test parsing first and last name."""
        first, last, key = _parse_name_parts("John Smith")
        assert first == "John"
        assert last == "Smith"
        assert key == "John Smith"

    def test_parse_three_part_name(self):
        """Test parsing first middle last (uses first and last only)."""
        first, last, key = _parse_name_parts("John Michael Smith")
        assert first == "John"
        assert last == "Smith"
        assert key == "John Smith"

    def test_parse_name_with_parentheses(self):
        """Test parsing names with parentheses like 'Weldeamlak\\n(Geza)'."""
        first, last, key = _parse_name_parts("Weldeamlak\n(Geza)")
        assert first == "Weldeamlak"
        assert last == "Geza"
        assert key == "Weldeamlak Geza"

    def test_parse_name_with_multiple_spaces(self):
        """Test parsing name with extra spaces (preserved in middle)."""
        first, last, key = _parse_name_parts("  John   Smith  ")
        assert first == "John"
        assert last == "Smith"
        # Note: _parse_name_parts preserves internal spacing
        assert "John" in key and "Smith" in key


class TestDuplicateDetection:
    """Test duplicate person detection."""

    def test_detect_no_duplicates_empty_set(self):
        """Test duplicate detection with empty rows list."""
        rows = []
        
        duplicates = detect_duplicates(rows)
        
        assert duplicates == []

    def test_build_people_set(self, tmp_path):
        """Test building people set from parsed rows."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,
Jane Smith,Spouse,John Doe,F,
Jack Doe,Child,John Doe,M,
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        people_dict = build_people_set(rows)
        
        # Returns dict keyed by person1_key
        assert len(people_dict) >= 3
        # Check that keys exist (person1_key values)
        assert "John Doe" in people_dict
        assert "Jane Smith" in people_dict
        assert "Jack Doe" in people_dict
        # Check display_name field (uses first name only)
        assert people_dict["John Doe"]["display_name"] == "John"
        assert people_dict["Jane Smith"]["display_name"] == "Jane"


class TestRelationshipBuilding:
    """Test relationship request building."""

    def test_build_relationship_requests(self, tmp_path):
        """Test building relationship requests from parsed rows."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,
Jane Smith,Spouse,John Doe,F,
Jack Doe,Child,John Doe,M,
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        people_dict = build_people_set(rows)
        
        # Create name map using person1_key (not display_name)
        name_map = {key: f"id_{i}" for i, key in enumerate(people_dict.keys())}
        
        rel_requests, warnings = build_relationship_requests(rows, name_map)
        
        # Should have relationships (at least CHILD_OF and SPOUSE_OF)
        assert len(rel_requests) >= 2


class TestJSONImport:
    """Test JSON format import."""

    def test_parse_valid_json_file(self, tmp_path):
        """Test parsing a valid JSON export file."""
        data = {
            "tree": {"id": 1, "name": "Test Tree", "description": "Test"},
            "tree_version": {"id": 1, "tree_id": 1, "version": 1},
            "people": [
                {"id": "p1", "display_name": "John Doe", "sex": "M", "notes": ""},
                {"id": "p2", "display_name": "Jane Smith", "sex": "F", "notes": "Wife"},
            ],
            "relationships": [
                {"id": "r1", "from_person_id": "p1", "to_person_id": None, "type": "EARLIEST_ANCESTOR"},
                {"id": "r2", "from_person_id": "p1", "to_person_id": "p2", "type": "SPOUSE_OF"},
            ]
        }
        
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data))
        
        parsed = parse_family_tree_json(file_path)
        
        assert parsed["tree"]["name"] == "Test Tree"
        assert len(parsed["people"]) == 2
        assert len(parsed["relationships"]) == 2

    def test_parse_json_file_not_found(self):
        """Test error handling for missing JSON file."""
        with pytest.raises(FileNotFoundError):
            parse_family_tree_json("/nonexistent/file.json")

    def test_parse_json_invalid_structure(self, tmp_path):
        """Test error handling for invalid JSON structure."""
        # JSON is an array instead of object
        data = ["not", "an", "object"]
        
        file_path = tmp_path / "invalid.json"
        file_path.write_text(json.dumps(data))
        
        with pytest.raises(ValueError, match="JSON root must be an object"):
            parse_family_tree_json(file_path)

    def test_parse_json_missing_people_key(self, tmp_path):
        """Test error handling for missing 'people' key."""
        data = {
            "tree": {"id": 1, "name": "Test"},
            "relationships": []
        }
        
        file_path = tmp_path / "missing_people.json"
        file_path.write_text(json.dumps(data))
        
        with pytest.raises(ValueError, match="must contain 'people' and 'relationships'"):
            parse_family_tree_json(file_path)

    def test_parse_json_people_not_array(self, tmp_path):
        """Test error handling when 'people' is not an array."""
        data = {
            "tree": {"id": 1, "name": "Test"},
            "people": "not an array",
            "relationships": []
        }
        
        file_path = tmp_path / "invalid_people.json"
        file_path.write_text(json.dumps(data))
        
        with pytest.raises(ValueError, match="'people' must be an array"):
            parse_family_tree_json(file_path)

    def test_extract_people_from_json(self):
        """Test extracting people from parsed JSON data."""
        data = {
            "people": [
                {"display_name": "John Doe", "sex": "M", "notes": "Patriarch"},
                {"display_name": "Jane Smith", "sex": "F", "notes": "Matriarch"},
                {"display_name": "Jack Doe", "sex": "U", "notes": ""},
            ]
        }
        
        people = extract_people_for_import(data)
        
        assert len(people) == 3
        assert "John Doe" in people
        assert people["John Doe"]["sex"] == "M"
        assert people["Jane Smith"]["sex"] == "F"

    def test_extract_people_normalizes_sex(self):
        """Test that invalid sex values are normalized to 'U'."""
        data = {
            "people": [
                {"display_name": "Person 1", "sex": "X", "notes": ""},
                {"display_name": "Person 2", "sex": "male", "notes": ""},
            ]
        }
        
        people = extract_people_for_import(data)
        
        # Invalid sex values should be normalized to "U"
        assert people["Person 1"]["sex"] == "U"
        assert people["Person 2"]["sex"] == "U"

    def test_extract_people_skips_empty_names(self):
        """Test that people with empty display names are skipped."""
        data = {
            "people": [
                {"display_name": "John Doe", "sex": "M", "notes": ""},
                {"display_name": "", "sex": "F", "notes": "Should be skipped"},
                {"display_name": "   ", "sex": "M", "notes": "Also skipped"},
            ]
        }
        
        people = extract_people_for_import(data)
        
        assert len(people) == 1
        assert "John Doe" in people


class TestImportWithDatabase:
    """Test import with actual database operations."""

    def test_import_creates_people(self, db_session: Session, sample_tree, sample_tree_version, tmp_path):
        """Test that text import creates people in database."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,Patriarch
Jane Smith,,,F,Matriarch
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        people_dict = build_people_set(rows)
        
        # Manually create people (simulating import process)
        from app import crud
        for unique_key, person_data in people_dict.items():
            crud.create_person(
                db_session,
                display_name=person_data["display_name"],
                sex=person_data["sex"],
                notes=person_data.get("notes", ""),
                tree_id=sample_tree.id,
                tree_version_id=sample_tree_version.id
            )
        
        # Query people
        people = db_session.query(Person).filter(
            Person.tree_version_id == sample_tree_version.id
        ).all()
        
        assert len(people) >= 2
        names = {p.display_name for p in people}
        # Display names use first name only
        assert "John" in names
        assert "Jane" in names

    def test_import_creates_relationships(self, db_session: Session, sample_tree, sample_tree_version, tmp_path):
        """Test that import creates relationships correctly."""
        content = """Person 1,Relation,Person 2,Gender,Details
John Doe,Earliest Ancestor,,M,
Jack Doe,Child,John Doe,M,
"""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        people_dict = build_people_set(rows)
        
        # Create people first
        from app import crud
        name_map = {}
        for unique_key, person_data in people_dict.items():
            person = crud.create_person(
                db_session,
                display_name=person_data["display_name"],
                sex=person_data["sex"],
                notes=person_data.get("notes", ""),
                tree_id=sample_tree.id,
                tree_version_id=sample_tree_version.id
            )
            # Map unique key to person ID
            name_map[unique_key] = person.id
        
        # Create relationships
        rel_requests, warnings = build_relationship_requests(rows, name_map)
        for line_no, req in rel_requests:
            crud.create_relationship(
                db_session,
                from_id=req["from_person_id"],
                to_id=req.get("to_person_id"),
                rel_type=req["type"],
                tree_id=sample_tree.id,
                tree_version_id=sample_tree_version.id
            )
        
        # Query relationships
        rels = db_session.query(Relationship).filter(
            Relationship.tree_version_id == sample_tree_version.id
        ).all()
        
        # Should have at least 1 CHILD_OF relationship
        assert len(rels) >= 1
        
        # Find the CHILD_OF relationship
        child_rel = next((r for r in rels if r.type == RelType.CHILD_OF), None)
        assert child_rel is not None
        assert child_rel.to_person_id is not None


class TestImportEdgeCases:
    """Test edge cases and error scenarios."""

    def test_import_empty_file(self, tmp_path):
        """Test importing an empty file."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")
        
        rows = parse_family_tree_txt(file_path)
        
        assert rows == []

    def test_import_only_comments(self, tmp_path):
        """Test importing file with only comments."""
        content = """# Comment 1
# Comment 2
# Comment 3
"""
        file_path = tmp_path / "comments_only.txt"
        file_path.write_text(content)
        
        rows = parse_family_tree_txt(file_path)
        
        assert rows == []

    def test_import_with_unicode_names(self, tmp_path):
        """Test importing file with unicode characters."""
        content = """Person 1,Relation,Person 2,Gender,Details
José María,Earliest Ancestor,,M,
François Müller,Child,José María,M,
"""
        file_path = tmp_path / "unicode.txt"
        file_path.write_text(content, encoding="utf-8")
        
        rows = parse_family_tree_txt(file_path)
        
        assert len(rows) == 2
        assert rows[0].person1 == "José María"
        assert rows[1].person1 == "François Müller"

    def test_json_import_with_null_values(self):
        """Test JSON import handles null values correctly."""
        data = {
            "people": [
                {"display_name": "John", "sex": "M", "notes": None},
                {"display_name": "Jane", "sex": "F", "notes": ""},
            ]
        }
        
        people = extract_people_for_import(data)
        
        assert len(people) == 2
        assert people["John"]["notes"] == ""
        assert people["Jane"]["notes"] == ""
