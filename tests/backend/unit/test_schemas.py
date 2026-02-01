"""
Unit tests for app/schemas.py - Pydantic schema validation.

Tests request/response schema validation and custom validators.
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    PersonCreate, PersonOut,
    RelCreate, RelationshipOut,
    TreeCreate, TreeFilter,
    TreeImportRequest,
)


class TestPersonCreateSchema:
    """Test PersonCreate validation."""

    def test_person_create_minimal(self):
        """Test creating person with minimal fields."""
        person = PersonCreate(display_name="John")
        assert person.display_name == "John"
        assert person.sex == "U"
        assert person.notes is None

    def test_person_create_all_fields(self):
        """Test creating person with all fields."""
        person = PersonCreate(
            display_name="Jane Doe",
            sex="F",
            notes="Matriarch",
            tree_id=1,
            tree_version_id=2
        )
        assert person.display_name == "Jane Doe"
        assert person.sex == "F"
        assert person.notes == "Matriarch"
        assert person.tree_id == 1
        assert person.tree_version_id == 2

    def test_person_create_requires_display_name(self):
        """Test PersonCreate requires display_name."""
        with pytest.raises(ValidationError) as exc_info:
            PersonCreate(sex="M")
        
        errors = exc_info.value.errors()
        assert any(e['loc'] == ('display_name',) for e in errors)

    def test_person_create_sex_defaults_to_u(self):
        """Test sex defaults to 'U'."""
        person = PersonCreate(display_name="Test")
        assert person.sex == "U"

    def test_person_create_invalid_sex(self):
        """Test invalid sex value raises error."""
        with pytest.raises(ValidationError):
            PersonCreate(display_name="Test", sex="X")


class TestPersonOutSchema:
    """Test PersonOut response schema."""

    def test_person_out_all_fields(self):
        """Test PersonOut with all fields."""
        person = PersonOut(
            id="p1",
            display_name="John",
            sex="M",
            notes="Test",
            tree_id=1,
            tree_version_id=1,
            version=1
        )
        assert person.id == "p1"
        assert person.display_name == "John"
        assert person.version == 1

    def test_person_out_minimal_fields(self):
        """Test PersonOut with minimal required fields."""
        person = PersonOut(
            id="p1",
            display_name="Jane",
            sex="F",
            version=2
        )
        assert person.id == "p1"
        assert person.display_name == "Jane"
        assert person.notes is None
        assert person.tree_id is None


class TestRelCreateSchema:
    """Test RelCreate validation with relationship constraints."""

    def test_rel_create_earliest_ancestor(self):
        """Test creating EARLIEST_ANCESTOR forces to_person_id to None."""
        rel = RelCreate(
            from_person_id="p1",
            to_person_id="p2",  # Will be set to None by validator
            type="EARLIEST_ANCESTOR",
            tree_id=1
        )
        # Validator should set it to None
        assert rel.to_person_id is None
        assert rel.type == "EARLIEST_ANCESTOR"

    def test_rel_create_child_of_requires_to_person(self):
        """Test CHILD_OF requires to_person_id."""
        with pytest.raises(ValidationError) as exc_info:
            RelCreate(
                from_person_id="p1",
                to_person_id=None,
                type="CHILD_OF"
            )
        
        errors = exc_info.value.errors()
        assert any("to_person_id is required" in str(e['msg']) for e in errors)

    def test_rel_create_spouse_of_requires_to_person(self):
        """Test SPOUSE_OF requires to_person_id."""
        with pytest.raises(ValidationError):
            RelCreate(
                from_person_id="p1",
                to_person_id=None,
                type="SPOUSE_OF"
            )

    def test_rel_create_child_of_valid(self):
        """Test valid CHILD_OF relationship."""
        rel = RelCreate(
            from_person_id="p_child",
            to_person_id="p_parent",
            type="CHILD_OF",
            tree_id=1
        )
        assert rel.from_person_id == "p_child"
        assert rel.to_person_id == "p_parent"
        assert rel.type == "CHILD_OF"

    def test_rel_create_spouse_of_valid(self):
        """Test valid SPOUSE_OF relationship."""
        rel = RelCreate(
            from_person_id="p1",
            to_person_id="p2",
            type="SPOUSE_OF",
            tree_id=1
        )
        assert rel.type == "SPOUSE_OF"

    def test_rel_create_requires_from_person_id(self):
        """Test RelCreate requires from_person_id."""
        with pytest.raises(ValidationError):
            RelCreate(
                to_person_id="p2",
                type="SPOUSE_OF"
            )

    def test_rel_create_requires_type(self):
        """Test RelCreate requires type."""
        with pytest.raises(ValidationError):
            RelCreate(
                from_person_id="p1",
                to_person_id="p2"
            )

    def test_rel_create_invalid_type(self):
        """Test invalid relationship type."""
        with pytest.raises(ValidationError):
            RelCreate(
                from_person_id="p1",
                to_person_id="p2",
                type="INVALID_TYPE"
            )


class TestRelationshipOutSchema:
    """Test RelationshipOut response schema."""

    def test_relationship_out_all_fields(self):
        """Test RelationshipOut with all fields."""
        rel = RelationshipOut(
            id="r1",
            from_person_id="p1",
            to_person_id="p2",
            type="CHILD_OF",
            tree_id=1,
            tree_version_id=1,
            version=1
        )
        assert rel.id == "r1"
        assert rel.from_person_id == "p1"
        assert rel.to_person_id == "p2"
        assert rel.version == 1

    def test_relationship_out_earliest_ancestor_null(self):
        """Test RelationshipOut with EARLIEST_ANCESTOR (null to_person_id)."""
        rel = RelationshipOut(
            id="r1",
            from_person_id="p1",
            to_person_id=None,
            type="EARLIEST_ANCESTOR",
            tree_id=1,
            tree_version_id=1,
            version=1
        )
        assert rel.to_person_id is None
        assert rel.type == "EARLIEST_ANCESTOR"


class TestTreeCreateSchema:
    """Test TreeCreate validation."""

    def test_tree_create_minimal(self):
        """Test creating tree with name only."""
        tree = TreeCreate(name="My Family")
        assert tree.name == "My Family"
        assert tree.description is None

    def test_tree_create_with_description(self):
        """Test creating tree with description."""
        tree = TreeCreate(name="Family", description="Multi-generational")
        assert tree.name == "Family"
        assert tree.description == "Multi-generational"

    def test_tree_create_requires_name(self):
        """Test TreeCreate requires name."""
        with pytest.raises(ValidationError):
            TreeCreate(description="No name")


class TestTreeFilterSchema:
    """Test TreeFilter schema."""

    def test_tree_filter_empty(self):
        """Test empty TreeFilter."""
        filter_obj = TreeFilter()
        assert filter_obj.tree_id is None
        assert filter_obj.tree_version_id is None

    def test_tree_filter_by_tree_id(self):
        """Test TreeFilter with tree_id."""
        filter_obj = TreeFilter(tree_id=1)
        assert filter_obj.tree_id == 1
        assert filter_obj.tree_version_id is None

    def test_tree_filter_by_version_id(self):
        """Test TreeFilter with tree_version_id."""
        filter_obj = TreeFilter(tree_version_id=5)
        assert filter_obj.tree_version_id == 5
        assert filter_obj.tree_id is None

    def test_tree_filter_both_provided(self):
        """Test TreeFilter with both IDs (version takes precedence)."""
        filter_obj = TreeFilter(tree_id=1, tree_version_id=5)
        assert filter_obj.tree_id == 1
        assert filter_obj.tree_version_id == 5


class TestTreeImportRequestSchema:
    """Test TreeImportRequest schema."""

    def test_import_request_minimal(self):
        """Test minimal import request."""
        req = TreeImportRequest()
        assert req.name is None
        assert req.source_filename is None
        assert req.tree_id is None

    def test_import_request_with_new_tree_name(self):
        """Test import request for new tree."""
        req = TreeImportRequest(name="Imported Family")
        assert req.name == "Imported Family"
        assert req.tree_id is None

    def test_import_request_for_new_version(self):
        """Test import request for new version of existing tree."""
        req = TreeImportRequest(tree_id=1, source_filename="family.txt")
        assert req.tree_id == 1
        assert req.source_filename == "family.txt"
        assert req.name is None
