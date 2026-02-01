"""
Unit tests for app/models.py - ORM model validation and constraints.

Tests SQLAlchemy models, relationships, and database constraints.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Person, Relationship, Tree, TreeVersion, Sex, RelType


class TestPersonModel:
    """Test Person model creation and validation."""

    def test_person_requires_display_name(self, db_session: Session):
        """Test that Person requires display_name."""
        person = Person(sex=Sex.M)
        db_session.add(person)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_person_sex_defaults_to_unknown(self, db_session: Session, sample_tree):
        """Test that sex defaults to 'U' (unknown)."""
        person = Person(
            display_name="Test",
            tree_id=sample_tree.id
        )
        db_session.add(person)
        db_session.commit()
        
        assert person.sex == Sex.U

    def test_person_with_all_fields(self, db_session: Session, sample_tree):
        """Test creating person with all fields populated."""
        person = Person(
            display_name="John Doe",
            sex=Sex.M,
            notes="Test patriarch",
            tree_id=sample_tree.id,
            tree_version_id=1
        )
        db_session.add(person)
        db_session.commit()
        
        assert person.display_name == "John Doe"
        assert person.sex == Sex.M
        assert person.notes == "Test patriarch"
        assert person.tree_id == sample_tree.id
        assert person.tree_version_id == 1

    def test_person_id_auto_generated(self, db_session: Session, sample_tree):
        """Test that person ID is auto-generated UUID."""
        person = Person(display_name="Test", tree_id=sample_tree.id)
        db_session.add(person)
        db_session.commit()
        
        assert person.id is not None
        assert len(person.id) == 36  # UUID string length with hyphens

    def test_person_version_defaults_to_one(self, db_session: Session, sample_tree):
        """Test that person version defaults to 1."""
        person = Person(display_name="Test", tree_id=sample_tree.id)
        db_session.add(person)
        db_session.commit()
        
        assert person.version == 1


class TestRelationshipModel:
    """Test Relationship model creation and constraints."""

    def test_relationship_requires_from_person(self, db_session: Session):
        """Test that Relationship requires from_person_id."""
        rel = Relationship(
            to_person_id="p2",
            type=RelType.CHILD_OF
        )
        db_session.add(rel)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_relationship_earliest_ancestor_null_to_person(self, db_session: Session, sample_person):
        """Test EARLIEST_ANCESTOR allows null to_person_id."""
        rel = Relationship(
            from_person_id=sample_person.id,
            to_person_id=None,  # Explicitly null
            type=RelType.EARLIEST_ANCESTOR
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.to_person_id is None
        assert rel.type == RelType.EARLIEST_ANCESTOR

    def test_relationship_child_of_requires_to_person(self, db_session: Session, sample_person, sample_person_child):
        """Test CHILD_OF requires to_person_id."""
        rel = Relationship(
            from_person_id=sample_person_child.id,
            to_person_id=sample_person.id,
            type=RelType.CHILD_OF
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.to_person_id is not None

    def test_relationship_spouse_of_requires_to_person(self, db_session: Session, sample_person, sample_person_female):
        """Test SPOUSE_OF requires to_person_id."""
        rel = Relationship(
            from_person_id=sample_person.id,
            to_person_id=sample_person_female.id,
            type=RelType.SPOUSE_OF
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.to_person_id is not None

    def test_relationship_id_auto_generated(self, db_session: Session, sample_person):
        """Test that relationship ID is auto-generated UUID."""
        rel = Relationship(
            from_person_id=sample_person.id,
            to_person_id=None,
            type=RelType.EARLIEST_ANCESTOR
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.id is not None
        assert len(rel.id) == 36

    def test_relationship_version_defaults_to_one(self, db_session: Session, sample_person):
        """Test that relationship version defaults to 1."""
        rel = Relationship(
            from_person_id=sample_person.id,
            to_person_id=None,
            type=RelType.EARLIEST_ANCESTOR
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.version == 1

    def test_relationship_with_tree_info(self, db_session: Session, sample_tree, sample_tree_version, sample_person):
        """Test relationship can be linked to tree and version."""
        rel = Relationship(
            from_person_id=sample_person.id,
            to_person_id=None,
            type=RelType.EARLIEST_ANCESTOR,
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        db_session.add(rel)
        db_session.commit()
        
        assert rel.tree_id == sample_tree.id
        assert rel.tree_version_id == sample_tree_version.id


class TestTreeModel:
    """Test Tree model."""

    def test_tree_requires_name(self, db_session: Session):
        """Test that Tree requires name."""
        tree = Tree()
        db_session.add(tree)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_tree_with_name_and_description(self, db_session: Session):
        """Test creating tree with name and description."""
        tree = Tree(name="Test Family", description="A test family tree")
        db_session.add(tree)
        db_session.commit()
        
        assert tree.name == "Test Family"
        assert tree.description == "A test family tree"
        assert tree.id is not None

    def test_tree_description_optional(self, db_session: Session):
        """Test that tree description is optional."""
        tree = Tree(name="Minimal Tree")
        db_session.add(tree)
        db_session.commit()
        
        assert tree.description is None


class TestTreeVersionModel:
    """Test TreeVersion model."""

    def test_tree_version_requires_tree_id(self, db_session: Session):
        """Test that TreeVersion requires tree_id."""
        version = TreeVersion(version=1)
        db_session.add(version)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_tree_version_active_defaults_true(self, db_session: Session, sample_tree):
        """Test that active defaults to True."""
        version = TreeVersion(tree_id=sample_tree.id, version=1)
        db_session.add(version)
        db_session.commit()
        
        assert version.active is True

    def test_tree_version_with_source_filename(self, db_session: Session, sample_tree):
        """Test tree version can store source filename."""
        version = TreeVersion(
            tree_id=sample_tree.id,
            version=1,
            source_filename="import.txt"
        )
        db_session.add(version)
        db_session.commit()
        
        assert version.source_filename == "import.txt"


class TestSexEnum:
    """Test Sex enum values."""

    def test_sex_enum_has_male(self):
        """Test Sex enum has M for male."""
        assert Sex.M.value == "M"

    def test_sex_enum_has_female(self):
        """Test Sex enum has F for female."""
        assert Sex.F.value == "F"

    def test_sex_enum_has_unknown(self):
        """Test Sex enum has U for unknown."""
        assert Sex.U.value == "U"


class TestRelTypeEnum:
    """Test RelType enum values."""

    def test_reltype_has_child_of(self):
        """Test RelType enum has CHILD_OF."""
        assert RelType.CHILD_OF.value == "CHILD_OF"

    def test_reltype_has_spouse_of(self):
        """Test RelType enum has SPOUSE_OF."""
        assert RelType.SPOUSE_OF.value == "SPOUSE_OF"

    def test_reltype_has_earliest_ancestor(self):
        """Test RelType enum has EARLIEST_ANCESTOR."""
        assert RelType.EARLIEST_ANCESTOR.value == "EARLIEST_ANCESTOR"


class TestModelRelationships:
    """Test SQLAlchemy relationship mappings."""

    def test_tree_has_versions(self, db_session: Session, sample_tree, sample_tree_version):
        """Test Tree.versions relationship."""
        assert len(sample_tree.versions) >= 1
        assert sample_tree_version in sample_tree.versions

    def test_relationship_from_person_reference(self, db_session: Session, sample_child_relationship):
        """Test Relationship.from_person relationship."""
        assert sample_child_relationship.from_person is not None
        assert sample_child_relationship.from_person.display_name == "Jack Doe"

    def test_relationship_to_person_reference(self, db_session: Session, sample_child_relationship):
        """Test Relationship.to_person relationship."""
        assert sample_child_relationship.to_person is not None
        assert sample_child_relationship.to_person.display_name == "John Doe"
