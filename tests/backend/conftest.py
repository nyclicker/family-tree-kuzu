"""
Pytest configuration and fixtures for backend testing.

Provides database setup, session management, and test data factories.
"""

import os
import pytest
import tempfile
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Set DATABASE_URL for app imports (even though tests use in-memory DB)
# This prevents KeyError when importing app.main
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Add parent directories to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from app.models import Base, Tree, TreeVersion, Person, Relationship, Sex, RelType


@pytest.fixture(scope="session")
def test_db_engine():
    """
    Create an in-memory SQLite database for testing.
    Scoped to session to avoid repeated setup.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db_engine):
    """
    Create a fresh database session for each test.
    Automatically rolls back changes after test.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_tree(db_session: Session) -> Tree:
    """Create a sample tree with basic structure."""
    tree = Tree(name="Test Family", description="A test family tree")
    db_session.add(tree)
    db_session.commit()
    db_session.refresh(tree)
    return tree


@pytest.fixture
def sample_tree_version(db_session: Session, sample_tree: Tree) -> TreeVersion:
    """Create a tree version for the sample tree."""
    version = TreeVersion(
        tree_id=sample_tree.id,
        version=1,
        source_filename="test.txt",
        active=True
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    return version


@pytest.fixture
def sample_person(db_session: Session, sample_tree: Tree, sample_tree_version: TreeVersion) -> Person:
    """Create a sample person."""
    person = Person(
        display_name="John Doe",
        sex=Sex.M,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
        notes="Patriarch"
    )
    db_session.add(person)
    db_session.commit()
    db_session.refresh(person)
    return person


@pytest.fixture
def sample_person_female(db_session: Session, sample_tree: Tree, sample_tree_version: TreeVersion) -> Person:
    """Create a sample female person."""
    person = Person(
        display_name="Jane Smith",
        sex=Sex.F,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
        notes="Matriarch"
    )
    db_session.add(person)
    db_session.commit()
    db_session.refresh(person)
    return person


@pytest.fixture
def sample_person_child(db_session: Session, sample_tree: Tree, sample_tree_version: TreeVersion) -> Person:
    """Create a sample child person."""
    person = Person(
        display_name="Jack Doe",
        sex=Sex.M,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
        notes="Son"
    )
    db_session.add(person)
    db_session.commit()
    db_session.refresh(person)
    return person


@pytest.fixture
def sample_earliest_ancestor_rel(
    db_session: Session, 
    sample_tree: Tree, 
    sample_tree_version: TreeVersion,
    sample_person: Person
) -> Relationship:
    """Create an EARLIEST_ANCESTOR relationship (root node)."""
    rel = Relationship(
        from_person_id=sample_person.id,
        to_person_id=None,  # Root node has no parent
        type=RelType.EARLIEST_ANCESTOR,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
    )
    db_session.add(rel)
    db_session.commit()
    db_session.refresh(rel)
    return rel


@pytest.fixture
def sample_child_relationship(
    db_session: Session,
    sample_tree: Tree,
    sample_tree_version: TreeVersion,
    sample_person: Person,
    sample_person_child: Person
) -> Relationship:
    """Create a CHILD_OF relationship."""
    rel = Relationship(
        from_person_id=sample_person_child.id,
        to_person_id=sample_person.id,
        type=RelType.CHILD_OF,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
    )
    db_session.add(rel)
    db_session.commit()
    db_session.refresh(rel)
    return rel


@pytest.fixture
def sample_spouse_relationship(
    db_session: Session,
    sample_tree: Tree,
    sample_tree_version: TreeVersion,
    sample_person: Person,
    sample_person_female: Person
) -> Relationship:
    """Create a SPOUSE_OF relationship."""
    rel = Relationship(
        from_person_id=sample_person.id,
        to_person_id=sample_person_female.id,
        type=RelType.SPOUSE_OF,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id,
    )
    db_session.add(rel)
    db_session.commit()
    db_session.refresh(rel)
    return rel


@pytest.fixture
def populated_tree(
    db_session: Session,
    sample_tree: Tree,
    sample_tree_version: TreeVersion,
    sample_person: Person,
    sample_person_female: Person,
    sample_person_child: Person,
    sample_earliest_ancestor_rel: Relationship,
    sample_spouse_relationship: Relationship,
    sample_child_relationship: Relationship,
) -> tuple[Tree, TreeVersion, list[Person], list[Relationship]]:
    """
    Return a fully populated tree with multiple people and relationships.
    Includes: patriarch, matriarch, child, root node, spouse link, child link.
    
    Returns tuple of (tree, tree_version, people, relationships).
    """
    people = [sample_person, sample_person_female, sample_person_child]
    relationships = [sample_earliest_ancestor_rel, sample_spouse_relationship, sample_child_relationship]
    return sample_tree, sample_tree_version, people, relationships


@pytest.fixture
def populated_fixture(populated_tree) -> tuple[Tree, TreeVersion, list[Person], list[Relationship]]:
    """Alias for populated_tree - returns (tree, tree_version, people, relationships)."""
    return populated_tree
