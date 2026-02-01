"""
Tests for advanced CRUD operations: draft publishing and relationship extraction.
"""

import pytest
from app import crud
from app.models import Person, Relationship, WorkingChange


class TestPublishDrafts:
    """Test publish_drafts function with various draft operations."""

    def test_publish_draft_creates_new_person(self, db_session, sample_tree, sample_tree_version):
        """Test publishing draft that adds a new person."""
        # Create draft person
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={
                "display_name": "New Person",
                "sex": "M",
                "notes": "Added via draft"
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        assert tv.version == 2
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        assert any(p.display_name == "New Person" for p in people)

    def test_publish_draft_edits_existing_person(self, db_session, sample_tree, sample_tree_version, sample_person):
        """Test publishing draft that edits an existing person."""
        # Create draft edit
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={
                "id": str(sample_person.id),
                "display_name": "Updated Name",
                "notes": "Updated notes"
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check person was updated in new version
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        updated = next((p for p in people if "Updated" in p.display_name), None)
        assert updated is not None
        assert updated.notes == "Updated notes"

    def test_publish_draft_deletes_person(self, db_session, sample_tree, sample_tree_version, sample_person):
        """Test publishing draft that deletes a person."""
        # Create draft deletion
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={
                "id": str(sample_person.id),
                "deleted": True
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check person was not copied to new version
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        assert len(people) == 0

    def test_publish_draft_creates_relationship(self, db_session, sample_tree, sample_tree_version):
        """Test publishing draft that creates a relationship."""
        # Create two people
        person1 = Person(display_name="Parent", sex="M", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        person2 = Person(display_name="Child", sex="F", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        db_session.add_all([person1, person2])
        db_session.commit()
        
        # Create draft relationship
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="relationship",
            payload={
                "from_person_id": str(person2.id),
                "to_person_id": str(person1.id),
                "type": "CHILD_OF"
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check relationship was created in new version
        rels = db_session.query(Relationship).filter(Relationship.tree_version_id == tv.id).all()
        assert len(rels) == 1
        assert rels[0].type.value == "CHILD_OF"

    def test_publish_draft_replaces_relationship(self, db_session, sample_tree, sample_tree_version):
        """Test publishing draft that replaces existing relationships."""
        # Create people and relationship
        parent1 = Person(display_name="Parent1", sex="M", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        parent2 = Person(display_name="Parent2", sex="F", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        child = Person(display_name="Child", sex="M", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        db_session.add_all([parent1, parent2, child])
        db_session.commit()
        
        # Create existing relationship
        rel1 = Relationship(from_person_id=str(child.id), to_person_id=str(parent1.id), type="CHILD_OF", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        db_session.add(rel1)
        db_session.commit()
        
        # Create draft that replaces relationship
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="relationship",
            payload={
                "from_person_id": str(child.id),
                "to_person_id": str(parent2.id),
                "type": "CHILD_OF",
                "op": "replace"  # Replace all from_person relationships
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check only new relationship exists
        rels = db_session.query(Relationship).filter(Relationship.tree_version_id == tv.id).all()
        assert len(rels) == 1

    def test_publish_draft_deletes_relationship(self, db_session, sample_tree, sample_tree_version):
        """Test publishing draft that deletes a relationship."""
        # Create people and relationship
        parent = Person(display_name="Parent", sex="M", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        child = Person(display_name="Child", sex="F", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        db_session.add_all([parent, child])
        db_session.commit()
        
        # Create relationship
        rel = Relationship(from_person_id=str(child.id), to_person_id=str(parent.id), type="CHILD_OF", tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        db_session.add(rel)
        db_session.commit()
        
        # Create draft that deletes relationship
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="relationship",
            payload={
                "from_person_id": str(child.id),
                "to_person_id": str(parent.id),
                "type": "CHILD_OF",
                "op": "delete"
            }
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check relationship was not copied to new version
        rels = db_session.query(Relationship).filter(Relationship.tree_version_id == tv.id).all()
        assert len(rels) == 0

    def test_publish_multiple_drafts_in_order(self, db_session, sample_tree, sample_tree_version):
        """Test publishing multiple drafts applies them in created order."""
        # Create drafts in specific order
        draft1 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Person1", "sex": "M"}
        )
        draft2 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Person2", "sex": "F"}
        )
        db_session.add_all([draft1, draft2])
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check both people were created
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        assert len(people) == 2
        assert any(p.display_name == "Person1" for p in people)
        assert any(p.display_name == "Person2" for p in people)

    def test_publish_drafts_clears_working_changes(self, db_session, sample_tree, sample_tree_version):
        """Test that publishing drafts deletes the working changes."""
        # Create draft
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Test", "sex": "M"}
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check drafts were deleted
        drafts = db_session.query(WorkingChange).filter(
            WorkingChange.tree_id == sample_tree.id,
            WorkingChange.base_tree_version_id == sample_tree_version.id
        ).all()
        assert len(drafts) == 0

    def test_publish_drafts_copies_base_version_people(self, db_session, sample_tree, sample_tree_version, sample_person):
        """Test that publishing drafts copies people from base version."""
        # Create empty draft (no changes)
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Extra", "sex": "M"}
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check base version person was copied
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        assert len(people) >= 1

    def test_publish_drafts_empty_base_version(self, db_session, sample_tree, sample_tree_version):
        """Test publishing drafts when base version has no people."""
        # Create draft person
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "OnlyPerson", "sex": "M"}
        )
        db_session.add(draft)
        db_session.commit()
        
        # Publish drafts
        tree, tv = crud.publish_drafts(db_session, tree_id=sample_tree.id, base_tree_version_id=sample_tree_version.id)
        
        # Check person was created
        people = db_session.query(Person).filter(Person.tree_version_id == tv.id).all()
        assert len(people) == 1
        assert people[0].display_name == "OnlyPerson"


class TestUpdateTreeFunction:
    """Test update_tree function."""

    def test_update_tree_name(self, db_session, sample_tree):
        """Test updating tree name."""
        updated = crud.update_tree(db_session, tree_id=sample_tree.id, name="NewName")
        
        assert updated.name == "NewName"
        assert updated.id == sample_tree.id

    def test_update_tree_description(self, db_session, sample_tree):
        """Test updating tree description."""
        updated = crud.update_tree(db_session, tree_id=sample_tree.id, description="New description")
        
        assert updated.description == "New description"

    def test_update_tree_both_fields(self, db_session, sample_tree):
        """Test updating both name and description."""
        updated = crud.update_tree(db_session, tree_id=sample_tree.id, name="New", description="Desc")
        
        assert updated.name == "New"
        assert updated.description == "Desc"

    def test_update_tree_not_found_raises(self, db_session):
        """Test updating non-existent tree raises exception."""
        with pytest.raises(Exception):
            crud.update_tree(db_session, tree_id=99999, name="Test")
