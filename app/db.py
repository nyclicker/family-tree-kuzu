"""KuzuDB embedded graph database connection."""
import kuzu
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph_data"
_database = None


def get_database():
    global _database
    if _database is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _database = kuzu.Database(str(DB_PATH))
        _init_schema(_database)
    return _database


def _init_schema(db):
    conn = kuzu.Connection(db)
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Person("
        "id STRING, display_name STRING, sex STRING, notes STRING, dataset STRING, "
        "PRIMARY KEY(id))"
    )
    conn.execute("CREATE REL TABLE IF NOT EXISTS PARENT_OF(FROM Person TO Person, id STRING)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS SPOUSE_OF(FROM Person TO Person, id STRING)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS SIBLING_OF(FROM Person TO Person, id STRING)")

    # Sharing: ShareLink → a shareable token for a dataset
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS ShareLink("
        "id STRING, dataset STRING, created_at STRING, "
        "PRIMARY KEY(id))"
    )
    # Viewer → someone allowed to view a shared link
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Viewer("
        "id STRING, email STRING, name STRING, "
        "PRIMARY KEY(id))"
    )
    # Access control: which viewers can see which share links
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS CAN_VIEW("
        "FROM Viewer TO ShareLink, granted_at STRING)"
    )
    # Access log: track every time a viewer opens a shared link
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS VIEWED("
        "FROM Viewer TO ShareLink, id STRING, viewed_at STRING, ip STRING)"
    )


def get_conn():
    db = get_database()
    conn = kuzu.Connection(db)
    try:
        yield conn
    finally:
        pass
