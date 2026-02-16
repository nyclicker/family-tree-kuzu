"""Shared fixtures for family-tree-kuzu test suite."""
import os

# Set env vars BEFORE any app imports
os.environ.setdefault("COOKIE_SECRET", "test-secret-key-for-testing")
os.environ.setdefault("SETUP_TOKEN", "test-setup-token")

import pytest
import kuzu
from fastapi.testclient import TestClient

from app.db import _init_schema, _migrate, get_conn
from app import auth, crud, trees, groups, sharing, changelog


# Ensure auth module uses test cookie secret
auth.COOKIE_SECRET = os.environ["COOKIE_SECRET"]


# ── CSV constants for import tests ──

SIMPLE_CSV = """\
Person 1,Relation,Person 2,Gender,Details
Grandpa,Earliest Ancestor,,M,The patriarch
Dad,Child,Grandpa,M,
Mom,Spouse,Dad,F,
Child1,Child,Dad,M,Young one
"""

DUPLICATE_NAMES_CSV = """\
Person 1,Relation,Person 2,Gender,Details
Alice,Earliest Ancestor,,F,
Bob,Earliest Ancestor,,M,
John,Child,Alice,M,
John,Child,Bob,M,
"""

SIBLING_CSV = """\
Person 1,Relation,Person 2,Gender,Details
Parent1,Earliest Ancestor,,M,
Child1,Child,Parent1,M,
Child2,Sibling,Child1,F,
"""

SPOUSE_MERGE_CSV = """\
Person 1,Relation,Person 2,Gender,Details
FatherA,Earliest Ancestor,,M,
ChildX,Child,FatherA,M,
MotherB,Earliest Ancestor,,F,
ChildX,Child,MotherB,,
FatherA,Spouse,MotherB,,
"""


# ── Database fixtures ──

@pytest.fixture
def db_path(tmp_path):
    """Temp directory for a fresh KuzuDB."""
    return tmp_path / "test_db"


@pytest.fixture
def db(db_path):
    """Initialized KuzuDB with full schema + migrations."""
    database = kuzu.Database(str(db_path))
    _init_schema(database)
    _migrate(database)
    return database


@pytest.fixture
def conn(db):
    """KuzuDB connection for unit tests."""
    return kuzu.Connection(db)


# ── User fixtures ──

@pytest.fixture
def user_alice(conn):
    """Admin user."""
    return auth.create_user(conn, "alice@example.com", "Alice Admin", "password123", is_admin=True)


@pytest.fixture
def user_bob(conn):
    """Non-admin user."""
    return auth.create_user(conn, "bob@example.com", "Bob User", "password456", is_admin=False)


@pytest.fixture
def user_carol(conn):
    """Second non-admin user."""
    return auth.create_user(conn, "carol@example.com", "Carol User", "password789", is_admin=False)


# ── Tree fixtures ──

@pytest.fixture
def tree_one(conn, user_alice):
    """Tree owned by Alice."""
    return trees.create_tree(conn, "Tree One", user_alice["id"])


@pytest.fixture
def tree_two(conn, user_bob):
    """Tree owned by Bob."""
    return trees.create_tree(conn, "Tree Two", user_bob["id"])


# ── Person fixtures ──

@pytest.fixture
def person_grandpa(conn, tree_one):
    return crud.create_person(conn, "Grandpa", "M", "The patriarch", tree_id=tree_one["id"])


@pytest.fixture
def person_dad(conn, tree_one):
    return crud.create_person(conn, "Dad", "M", tree_id=tree_one["id"])


@pytest.fixture
def person_mom(conn, tree_one):
    return crud.create_person(conn, "Mom", "F", tree_id=tree_one["id"])


@pytest.fixture
def person_child(conn, tree_one):
    return crud.create_person(conn, "Child", "U", tree_id=tree_one["id"])


@pytest.fixture
def family_graph(conn, tree_one, person_grandpa, person_dad, person_mom, person_child):
    """Connected family: grandpa->dad, dad->child, mom->child, dad<->mom (spouse)."""
    crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF")
    crud.create_relationship(conn, person_dad["id"], person_child["id"], "PARENT_OF")
    crud.create_relationship(conn, person_mom["id"], person_child["id"], "PARENT_OF")
    crud.create_relationship(conn, person_dad["id"], person_mom["id"], "SPOUSE_OF")
    return {
        "grandpa": person_grandpa,
        "dad": person_dad,
        "mom": person_mom,
        "child": person_child,
        "tree": tree_one,
    }


# ── FastAPI app fixtures ──

@pytest.fixture
def app_with_db(db):
    """FastAPI app with dependency override pointing at test DB."""
    # Import the app fresh — auth.COOKIE_SECRET already set above
    from app.main import app

    def override_get_conn():
        c = kuzu.Connection(db)
        try:
            yield c
        finally:
            pass

    app.dependency_overrides[get_conn] = override_get_conn
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_db):
    """Unauthenticated TestClient."""
    return TestClient(app_with_db, raise_server_exceptions=False)


def _make_authenticated_client(app, db, email, display_name, password, is_admin=False):
    """Helper: create a user and return an authenticated TestClient."""
    c = kuzu.Connection(db)
    try:
        user = auth.create_user(c, email, display_name, password, is_admin=is_admin)
    except ValueError:
        user = auth.get_user_by_email(c, email)
    token = auth.create_session_token(user["id"])
    tc = TestClient(app, raise_server_exceptions=False, cookies={"session": token})
    tc._test_user = user
    return tc


@pytest.fixture
def auth_client(app_with_db, db):
    """Admin-authenticated TestClient (Alice)."""
    return _make_authenticated_client(
        app_with_db, db, "alice@test.com", "Alice", "password123", is_admin=True
    )


@pytest.fixture
def viewer_client(app_with_db, db):
    """Viewer-authenticated TestClient (Eve — non-admin)."""
    return _make_authenticated_client(
        app_with_db, db, "eve@test.com", "Eve Viewer", "password000", is_admin=False
    )


@pytest.fixture
def make_authenticated_client(app_with_db, db):
    """Factory fixture: returns a callable to create authenticated TestClients."""
    def _factory(email, display_name, password, is_admin=False):
        return _make_authenticated_client(app_with_db, db, email, display_name, password, is_admin)
    return _factory
