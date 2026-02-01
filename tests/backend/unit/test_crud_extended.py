"""
Additional CRUD operation tests for update/delete and tree management.

These tests increase coverage of crud.py beyond the basic create/list operations.
"""

import pytest
from sqlalchemy.orm import Session

from app import crud
from app.models import Person, Relationship, Tree, TreeVersion, Sex, RelType


class TestGetPerson:
    """Test getting individual people."""

    def test_get_person_exists(self, db_session, sample_person):
        """Test getting an existing person."""
        person = crud.get_person(db_session, str(sample_person.id))
        
        assert person is not None
        assert person.id == sample_person.id
        assert person.display_name == sample_person.display_name

    def test_get_person_not_found(self, db_session):
        """Test getting non-existent person returns None."""
        import uuid
        fake_id = str(uuid.uuid4())
        
        person = crud.get_person(db_session, fake_id)
        
        assert person is None


class TestUpdatePerson:
    """Test updating person fields."""

    def test_update_person_display_name(self, db_session, sample_person):
        """Test updating display name."""
        original_name = sample_person.display_name
        new_name = "Updated Name"
        
        updated = crud.update_person(db_session, str(sample_person.id), {
            "display_name": new_name
        })
        
        assert updated is not None
        assert updated.display_name == new_name
        assert updated.display_name != original_name

    def test_update_person_sex(self, db_session, sample_person):
        """Test updating sex."""
        updated = crud.update_person(db_session, str(sample_person.id), {
            "sex": "F"
        })
        
        assert updated is not None
        assert updated.sex == Sex.F

    def test_update_person_notes(self, db_session, sample_person):
        """Test updating notes."""
        new_notes = "Updated notes text"
        
        updated = crud.update_person(db_session, str(sample_person.id), {
            "notes": new_notes
        })
        
        assert updated is not None
        assert updated.notes == new_notes

    def test_update_person_multiple_fields(self, db_session, sample_person):
        """Test updating multiple fields at once."""
        updates = {
            "display_name": "New Name",
            "sex": "F",
            "notes": "New notes"
        }
        
        updated = crud.update_person(db_session, str(sample_person.id), updates)
        
        assert updated is not None
        assert updated.display_name == "New Name"
        assert updated.sex == Sex.F
        assert updated.notes == "New notes"

    def test_update_person_not_found(self, db_session):
        """Test updating non-existent person returns None."""
        import uuid
        fake_id = str(uuid.uuid4())
        
        result = crud.update_person(db_session, fake_id, {"display_name": "Test"})
        
        assert result is None

    def test_update_person_invalid_field_ignored(self, db_session, sample_person):
        """Test that invalid fields are ignored."""
        updated = crud.update_person(db_session, str(sample_person.id), {
            "invalid_field": "value",
            "display_name": "Valid Update"
        })
        
        assert updated is not None
        assert updated.display_name == "Valid Update"
        assert not hasattr(updated, "invalid_field")


class TestDeletePerson:
    """Test deleting people."""

    def test_delete_person_success(self, db_session, sample_tree, sample_tree_version):
        """Test deleting a person."""
        # Create a person to delete
        person = crud.create_person(
            db_session,
            display_name="To Delete",
            sex="M",
            notes="",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        person_id = str(person.id)
        
        result = crud.delete_person(db_session, person_id)
        
        assert result is True
        # Verify person is gone
        assert crud.get_person(db_session, person_id) is None

    def test_delete_person_cascades_relationships(self, db_session, populated_tree):
        """Test that deleting a person also deletes their relationships."""
        tree, tree_version, people, relationships = populated_tree
        person_id = str(people[0].id)
        
        # Count relationships before
        initial_rel_count = len(crud.list_relationships(db_session, tree_version_id=tree_version.id))
        
        result = crud.delete_person(db_session, person_id)
        
        assert result is True
        # Verify relationships reduced
        final_rel_count = len(crud.list_relationships(db_session, tree_version_id=tree_version.id))
        assert final_rel_count < initial_rel_count

    def test_delete_person_not_found(self, db_session):
        """Test deleting non-existent person returns False."""
        import uuid
        fake_id = str(uuid.uuid4())
        
        result = crud.delete_person(db_session, fake_id)
        
        assert result is False


class TestGetRelationship:
    """Test getting individual relationships."""

    def test_get_relationship_exists(self, db_session, sample_earliest_ancestor_rel):
        """Test getting an existing relationship."""
        rel = crud.get_relationship(db_session, str(sample_earliest_ancestor_rel.id))
        
        assert rel is not None
        assert rel.id == sample_earliest_ancestor_rel.id
        assert rel.type == RelType.EARLIEST_ANCESTOR

    def test_get_relationship_not_found(self, db_session):
        """Test getting non-existent relationship returns None."""
        import uuid
        fake_id = str(uuid.uuid4())
        
        rel = crud.get_relationship(db_session, fake_id)
        
        assert rel is None


class TestDeleteRelationship:
    """Test deleting relationships."""

    def test_delete_relationship_success(self, db_session, populated_tree):
        """Test deleting a relationship."""
        tree, tree_version, people, relationships = populated_tree
        rel_id = str(relationships[1].id)  # Use spouse relationship
        
        result = crud.delete_relationship(db_session, rel_id)
        
        assert result is True
        # Verify relationship is gone
        assert crud.get_relationship(db_session, rel_id) is None

    def test_delete_relationship_not_found(self, db_session):
        """Test deleting non-existent relationship returns False."""
        import uuid
        fake_id = str(uuid.uuid4())
        
        result = crud.delete_relationship(db_session, fake_id)
        
        assert result is False


class TestTreeManagement:
    """Tests for tree and version management functions."""
    
    def test_create_or_increment_new_tree(self, db_session):
        """Test creating a new tree with first version."""
        tree, version = crud.create_or_increment_tree_version(
            db_session, 
            name="TestTree", 
            source_filename="test.txt"
        )
        assert tree.name == "TestTree"
        assert tree.id is not None
        assert version.version == 1
        assert version.active is True
        assert version.source_filename == "test.txt"
    
    def test_create_or_increment_existing_tree(self, db_session, sample_tree, sample_tree_version):
        """Test incrementing version for existing tree."""
        tree, version = crud.create_or_increment_tree_version(
            db_session, 
            name="NewVersion",
            source_filename="test2.txt",
            tree_id=sample_tree.id
        )
        assert tree.id == sample_tree.id
        assert version.version == 2  # Should increment
        assert version.active is True
        
        # Old version should be deactivated
        db_session.refresh(sample_tree_version)
        assert sample_tree_version.active is False

    def test_create_or_increment_tree_missing_id_raises(self, db_session):
        """Test missing tree_id raises error."""
        with pytest.raises(ValueError, match="Tree id .* not found"):
            crud.create_or_increment_tree_version(
                db_session,
                name=None,
                source_filename="missing.txt",
                tree_id=99999,
            )

    def test_create_or_increment_tree_fallback_name(self, db_session):
        """Test fallback tree name from source filename."""
        tree, version = crud.create_or_increment_tree_version(
            db_session,
            name=None,
            source_filename="fallback.txt",
        )
        assert tree.name == "fallback.txt"
        assert version.version == 1
    
    def test_update_tree(self, db_session, sample_tree):
        """Test updating tree metadata."""
        updated = crud.update_tree(
            db_session, 
            tree_id=sample_tree.id,
            name="Updated Name",
            description="Updated description"
        )
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"


class TestDraftManagement:
    """Test working changes (draft) CRUD operations."""

    def test_create_draft_person(self, db_session, sample_tree, sample_tree_version):
        """Test creating a draft person change."""
        payload = {
            "display_name": "Draft Person",
            "sex": "M",
            "notes": "Draft notes"
        }
        
        draft = crud.create_draft(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload=payload
        )
        
        assert draft is not None
        assert draft.change_type == "person"
        assert draft.payload["display_name"] == "Draft Person"
        # Should have assigned draft_person_id
        assert "draft_person_id" in draft.payload

    def test_create_draft_relationship(self, db_session, sample_tree, sample_tree_version):
        """Test creating a draft relationship change."""
        payload = {
            "from_person_id": "some-id",
            "to_person_id": "other-id",
            "type": "CHILD_OF"
        }
        
        draft = crud.create_draft(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="relationship",
            payload=payload
        )
        
        assert draft is not None
        assert draft.change_type == "relationship"

    def test_list_drafts(self, db_session, sample_tree, sample_tree_version):
        """Test listing drafts."""
        # Create a draft first
        crud.create_draft(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Test"}
        )
        
        drafts = crud.list_drafts(db_session, tree_id=sample_tree.id)
        
        assert len(drafts) >= 1

    def test_delete_draft(self, db_session, sample_tree, sample_tree_version):
        """Test deleting a single draft."""
        # Create a draft
        draft = crud.create_draft(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Test"}
        )
        draft_id = draft.id
        
        crud.delete_draft(db_session, draft_id)
        
        # Verify draft is gone
        drafts = crud.list_drafts(db_session, tree_id=sample_tree.id)
        assert not any(d.id == draft_id for d in drafts)

    def test_delete_drafts_for_base(self, db_session, sample_tree, sample_tree_version):
        """Test deleting all drafts for a base version."""
        # Create multiple drafts
        for i in range(3):
            crud.create_draft(
                db_session,
                tree_id=sample_tree.id,
                base_tree_version_id=sample_tree_version.id,
                change_type="person",
                payload={"display_name": f"Test {i}"}
            )
        
        count = crud.delete_drafts_for_base(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id
        )
        
        assert count >= 3
        # Verify all drafts are gone
        remaining = crud.list_drafts(
            db_session,
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id
        )
        assert len(remaining) == 0
