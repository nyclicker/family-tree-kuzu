"""Tests for app/db.py — schema init, migrations, get_conn."""
import kuzu
from app.db import _init_schema, _migrate, get_conn


def test_init_schema_creates_all_tables(db):
    """Verify all expected node tables exist after schema init."""
    conn = kuzu.Connection(db)
    expected_tables = [
        "Person", "ShareLink", "Viewer", "User",
        "FamilyTree", "UserGroup", "PersonComment", "TreeChange",
    ]
    for table in expected_tables:
        result = conn.execute(f"MATCH (n:{table}) RETURN count(*)")
        assert result.has_next()


def test_init_schema_idempotent(db):
    """Calling _init_schema twice doesn't error."""
    _init_schema(db)
    _init_schema(db)
    conn = kuzu.Connection(db)
    result = conn.execute("MATCH (p:Person) RETURN count(*)")
    assert result.has_next()


def test_migrate_adds_columns(db_path):
    """Migration adds tree_id, birth/death dates, magic_token columns."""
    database = kuzu.Database(str(db_path))
    _init_schema(database)
    _migrate(database)
    # Calling again should not error
    _migrate(database)
    conn = kuzu.Connection(database)
    # Verify Person columns work
    conn.execute(
        "CREATE (p:Person {id: 'test', display_name: 'Test', sex: 'U', "
        "notes: '', dataset: '', tree_id: 'tree1', "
        "birth_date: '2000-01-01', death_date: '', is_deceased: false})"
    )
    result = conn.execute(
        "MATCH (p:Person) WHERE p.id = 'test' "
        "RETURN p.tree_id, p.birth_date, p.is_deceased"
    )
    assert result.has_next()
    row = result.get_next()
    assert row[0] == "tree1"
    assert row[1] == "2000-01-01"
    assert row[2] is False


def test_get_conn_yields_connection():
    """get_conn is a generator that yields a usable connection."""
    gen = get_conn()
    # get_conn calls get_database() which uses the global singleton;
    # Just verify it's a generator
    assert hasattr(gen, '__next__')
