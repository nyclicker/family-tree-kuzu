"""KuzuDB embedded graph database connection."""
import os
import kuzu
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent.parent / "graph_data"))
_database = None


def get_database():
    global _database
    if _database is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _database = kuzu.Database(str(DB_PATH))
        _init_schema(_database)
        _migrate(_database)
    return _database


def _init_schema(db):
    conn = kuzu.Connection(db)

    # ── Core data tables ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Person("
        "id STRING, display_name STRING, sex STRING, notes STRING, "
        "dataset STRING, tree_id STRING, "
        "PRIMARY KEY(id))"
    )
    conn.execute("CREATE REL TABLE IF NOT EXISTS PARENT_OF(FROM Person TO Person, id STRING)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS SPOUSE_OF(FROM Person TO Person, id STRING)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS SIBLING_OF(FROM Person TO Person, id STRING)")

    # ── Sharing tables ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS ShareLink("
        "id STRING, dataset STRING, tree_id STRING, created_at STRING, "
        "PRIMARY KEY(id))"
    )
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Viewer("
        "id STRING, email STRING, name STRING, "
        "PRIMARY KEY(id))"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS CAN_VIEW("
        "FROM Viewer TO ShareLink, granted_at STRING)"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS VIEWED("
        "FROM Viewer TO ShareLink, id STRING, viewed_at STRING, ip STRING)"
    )

    # ── User & Auth tables ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS User("
        "id STRING, email STRING, display_name STRING, "
        "password_hash STRING, is_admin BOOL, created_at STRING, "
        "PRIMARY KEY(id))"
    )

    # ── FamilyTree table ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS FamilyTree("
        "id STRING, name STRING, created_at STRING, "
        "PRIMARY KEY(id))"
    )

    # ── UserGroup table ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS UserGroup("
        "id STRING, name STRING, `description` STRING, "
        "created_by STRING, created_at STRING, "
        "PRIMARY KEY(id))"
    )

    # ── PersonComment table ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS PersonComment("
        "id STRING, person_id STRING, tree_id STRING, "
        "author_id STRING, author_name STRING, content STRING, "
        "created_at STRING, "
        "PRIMARY KEY(id))"
    )

    # ── Relationship tables for entitlements ──
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS OWNS("
        "FROM User TO FamilyTree)"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS CAN_ACCESS("
        "FROM User TO FamilyTree, role STRING, granted_at STRING)"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS MEMBER_OF("
        "FROM User TO UserGroup, added_at STRING)"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS GROUP_CAN_ACCESS("
        "FROM UserGroup TO FamilyTree, role STRING, granted_at STRING)"
    )


def _migrate(db):
    """Run migrations for existing databases that need new columns/tables."""
    conn = kuzu.Connection(db)

    # Add tree_id column to Person if it doesn't exist
    try:
        conn.execute("ALTER TABLE Person ADD tree_id STRING DEFAULT ''")
    except Exception:
        pass  # column already exists

    # Add tree_id column to ShareLink if it doesn't exist
    try:
        conn.execute("ALTER TABLE ShareLink ADD tree_id STRING DEFAULT ''")
    except Exception:
        pass  # column already exists

    # Add birth_date, death_date, is_deceased to Person
    for col, default in [("birth_date", "''"), ("death_date", "''"), ("is_deceased", "false")]:
        try:
            conn.execute(f"ALTER TABLE Person ADD {col} {'BOOL' if col == 'is_deceased' else 'STRING'} DEFAULT {default}")
        except Exception:
            pass  # column already exists

    # Add magic_token to User (for magic link login)
    try:
        conn.execute("ALTER TABLE User ADD magic_token STRING DEFAULT ''")
    except Exception:
        pass  # column already exists


def get_conn():
    db = get_database()
    conn = kuzu.Connection(db)
    try:
        yield conn
    finally:
        pass
