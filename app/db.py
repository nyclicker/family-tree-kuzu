"""KuzuDB embedded graph database connection."""
import os
import logging
import kuzu
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent.parent / "graph_data"))
_database = None
_SENTINEL_FILE = ".db_initialized"


def _sentinel_path():
    return DB_PATH.parent / _SENTINEL_FILE


def write_sentinel():
    """Write a sentinel file indicating the database has been initialized with data.
    Called after the first user registers so we can detect silent DB resets."""
    try:
        path = _sentinel_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("initialized")
        logger.info("Database sentinel written to %s", path)
    except Exception as e:
        logger.warning("Could not write DB sentinel: %s", e)


def check_db_integrity(conn):
    """Check if the database was silently reset (e.g., persistent disk not mounted).
    If a sentinel file exists but the DB has 0 users, data was likely lost."""
    sentinel = _sentinel_path()
    if not sentinel.exists():
        return  # First-time setup, nothing to check
    # Sentinel exists — we previously had data. Verify users still exist.
    try:
        result = conn.execute("MATCH (u:User) RETURN count(*)")
        count = result.get_next()[0] if result.has_next() else 0
        if count == 0:
            logger.critical(
                "DATABASE INTEGRITY CHECK FAILED: Sentinel file exists at %s "
                "but database has 0 users. The persistent disk may not be mounted. "
                "Refusing to serve requests to prevent data loss.",
                sentinel
            )
            raise RuntimeError(
                "Database was previously initialized but now has 0 users. "
                "This likely means the persistent disk is not mounted. "
                "Check your deployment configuration."
            )
        logger.info("Database integrity check passed: %d users found", count)
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("Could not run DB integrity check: %s", e)


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
        "id STRING, name STRING, descr STRING, "
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

    # ── TreeChange (audit log) ──
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS TreeChange("
        "id STRING, tree_id STRING, user_id STRING, user_name STRING, "
        "action STRING, entity_type STRING, entity_id STRING, "
        "details STRING, created_at STRING, "
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

    # Rename UserGroup.description -> descr (description is a reserved keyword)
    try:
        conn.execute("ALTER TABLE UserGroup RENAME description TO descr")
    except Exception:
        pass  # already renamed or column doesn't exist


def get_conn():
    db = get_database()
    conn = kuzu.Connection(db)
    try:
        yield conn
    finally:
        pass
