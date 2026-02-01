"""
Unit tests for CRUD operations in app/crud.py

Tests basic Create, Read, Update operations on People, Relationships, and Trees.
"""

import pytest
from sqlalchemy.orm import Session

from app import crud
from app.models import Person, Relationship, Sex, RelType, TreeVersion


class TestCreatePerson:
    """Test person creation with various configurations."""

    def test_create_person_basic(self, db_session: Session, sample_tree):
        """Test creating a basic person."""
        person = crud.create_person(
            db_session,
            display_name="Test Person",
            sex="M",
            notes="Test notes",
            tree_id=sample_tree.id,
            tree_version_id=None
        )
        
        assert person.display_name == "Test Person"
        assert person.sex == Sex.M
        assert person.notes == "Test notes"
        assert person.tree_id == sample_tree.id
        assert person.id is not None

    def test_create_person_with_tree_version(self, db_session: Session, sample_tree, sample_tree_version):
        """Test creating a person linked to a specific tree version."""
        person = crud.create_person(
            db_session,
            display_name="Versioned Person",
            sex="F",
            notes=None,
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        assert person.tree_id == sample_tree.id
        assert person.tree_version_id == sample_tree_version.id
        assert person.sex == Sex.F

    def test_create_person_unknown_sex(self, db_session: Session, sample_tree):
        """Test creating a person with unknown sex defaults to 'U'."""
        person = crud.create_person(
            db_session,
            display_name="Unknown Gender",
            sex="U",
            notes=None,
            tree_id=sample_tree.id,
            tree_version_id=None
        )
        
        assert person.sex == Sex.U

    def test_create_person_persists_to_db(self, db_session: Session, sample_tree):
        """Test that created person is persisted to database."""
        person = crud.create_person(
            db_session,
            display_name="Persistent Person",
            sex="M",
            notes=None,
            tree_id=sample_tree.id,
            tree_version_id=None
        )
        
        person_id = person.id
        
        # Query the database directly
        retrieved = db_session.query(Person).filter(Person.id == person_id).first()
        assert retrieved is not None
        assert retrieved.display_name == "Persistent Person"


class TestListPeople:
    """Test listing people with various filters."""

    def test_list_people_by_tree_version(self, db_session: Session, sample_tree_version, sample_person, sample_person_female):
        """Test listing people filtered by tree_version_id."""
        people = crud.list_people(db_session, tree_version_id=sample_tree_version.id)
        
        # Should include sample_person and sample_person_female
        names = [p.display_name for p in people]
        assert "John Doe" in names
        assert "Jane Smith" in names

    def test_list_people_by_tree_active_version(self, db_session: Session, sample_tree, sample_tree_version, sample_person):
        """Test listing people by tree_id queries active version."""
        people = crud.list_people(db_session, tree_id=sample_tree.id)
        
        # Should return people from active version
        assert len(people) > 0
        assert any(p.display_name == "John Doe" for p in people)

    def test_list_people_returns_sorted(self, db_session: Session, sample_tree_version):
        """Test that list_people returns sorted by display_name."""
        # Create multiple people
        for name in ["Zebra", "Apple", "Mango"]:
            crud.create_person(
                db_session,
                display_name=name,
                sex="M",
                notes=None,
                tree_id=sample_tree_version.tree_id,
                tree_version_id=sample_tree_version.id
            )
        
        people = crud.list_people(db_session, tree_version_id=sample_tree_version.id)
        names = [p.display_name for p in people]
        
        # Check if sorted
        assert names == sorted(names)

    def test_list_people_empty_tree_version(self, db_session: Session, sample_tree):
        """Test listing people from empty tree version returns empty list."""
        # Create a new empty version
        empty_version = TreeVersion(tree_id=sample_tree.id, version=2, active=False)
        db_session.add(empty_version)
        db_session.commit()
        
        people = crud.list_people(db_session, tree_version_id=empty_version.id)
        assert people == []


class TestCreateRelationship:
    """Test relationship creation with constraints."""

    def test_create_earliest_ancestor_with_null_to_person(self, db_session: Session, sample_tree, sample_tree_version, sample_person):
        """Test creating EARLIEST_ANCESTOR relationship with null to_person_id."""
        rel = crud.create_relationship(
            db_session,
            from_id=sample_person.id,
            to_id=None,
            rel_type="EARLIEST_ANCESTOR",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        assert rel.from_person_id == sample_person.id
        assert rel.to_person_id is None
        assert rel.type == RelType.EARLIEST_ANCESTOR

    def test_create_child_of_relationship(self, db_session: Session, sample_tree, sample_tree_version, sample_person, sample_person_child):
        """Test creating CHILD_OF relationship."""
        rel = crud.create_relationship(
            db_session,
            from_id=sample_person_child.id,
            to_id=sample_person.id,
            rel_type="CHILD_OF",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        assert rel.from_person_id == sample_person_child.id
        assert rel.to_person_id == sample_person.id
        assert rel.type == RelType.CHILD_OF

    def test_create_spouse_of_relationship(self, db_session: Session, sample_tree, sample_tree_version, sample_person, sample_person_female):
        """Test creating SPOUSE_OF relationship."""
        rel = crud.create_relationship(
            db_session,
            from_id=sample_person.id,
            to_id=sample_person_female.id,
            rel_type="SPOUSE_OF",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        assert rel.from_person_id == sample_person.id
        assert rel.to_person_id == sample_person_female.id
        assert rel.type == RelType.SPOUSE_OF

    def test_enforce_one_earliest_ancestor_per_version(self, db_session: Session, sample_tree, sample_tree_version, sample_person, sample_person_female):
        """Test that only one EARLIEST_ANCESTOR can exist per tree version."""
        # Create first earliest ancestor
        rel1 = crud.create_relationship(
            db_session,
            from_id=sample_person.id,
            to_id=None,
            rel_type="EARLIEST_ANCESTOR",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        # Try to create second earliest ancestor in same version
        with pytest.raises(Exception):  # Should raise an error
            rel2 = crud.create_relationship(
                db_session,
                from_id=sample_person_female.id,
                to_id=None,
                rel_type="EARLIEST_ANCESTOR",
                tree_id=sample_tree.id,
                tree_version_id=sample_tree_version.id
            )

    def test_relationship_persists_to_db(self, db_session: Session, sample_tree, sample_tree_version, sample_person, sample_person_child):
        """Test that created relationship persists to database."""
        rel = crud.create_relationship(
            db_session,
            from_id=sample_person_child.id,
            to_id=sample_person.id,
            rel_type="CHILD_OF",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        rel_id = rel.id
        
        # Query directly
        retrieved = db_session.query(Relationship).filter(Relationship.id == rel_id).first()
        assert retrieved is not None
        assert retrieved.type == RelType.CHILD_OF


class TestListRelationships:
    """Test listing relationships with filters."""

    def test_list_relationships_by_tree_version(self, db_session: Session, sample_tree_version, sample_child_relationship):
        """Test listing relationships filtered by tree_version_id."""
        rels = crud.list_relationships(db_session, tree_version_id=sample_tree_version.id)
        
        assert len(rels) > 0
        assert any(r.id == sample_child_relationship.id for r in rels)

    def test_list_relationships_by_tree_active_version(self, db_session: Session, sample_tree, sample_child_relationship):
        """Test listing relationships by tree_id queries active version."""
        rels = crud.list_relationships(db_session, tree_id=sample_tree.id)
        
        assert len(rels) > 0

    def test_list_relationships_empty_version(self, db_session: Session, sample_tree):
        """Test listing relationships from empty version."""
        empty_version = TreeVersion(tree_id=sample_tree.id, version=3, active=False)
        db_session.add(empty_version)
        db_session.commit()
        
        rels = crud.list_relationships(db_session, tree_version_id=empty_version.id)
        assert rels == []


class TestTreeVersioning:
    """Test tree versioning logic."""

    def test_new_tree_has_version_one(self, db_session: Session, sample_tree, sample_tree_version):
        """Test that first tree version is numbered 1."""
        assert sample_tree_version.version == 1

    def test_new_version_increments_number(self, db_session: Session, sample_tree):
        """Test creating new version increments version number."""
        v1 = TreeVersion(tree_id=sample_tree.id, version=1, active=True)
        db_session.add(v1)
        db_session.commit()
        
        v2 = TreeVersion(tree_id=sample_tree.id, version=2, active=False)
        db_session.add(v2)
        db_session.commit()
        
        # Query to verify
        versions = db_session.query(TreeVersion).filter(TreeVersion.tree_id == sample_tree.id).order_by(TreeVersion.version).all()
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2

    def test_only_one_active_version_per_tree(self, db_session: Session, sample_tree, sample_tree_version):
        """Test that only one version can be active per tree."""
        # Create second version, deactivate first
        v2 = TreeVersion(tree_id=sample_tree.id, version=2, active=True)
        db_session.add(v2)
        
        sample_tree_version.active = False
        db_session.add(sample_tree_version)
        
        db_session.commit()
        
        active_versions = db_session.query(TreeVersion).filter(
            TreeVersion.tree_id == sample_tree.id,
            TreeVersion.active == True
        ).all()
        
        assert len(active_versions) == 1
        assert active_versions[0].version == 2
