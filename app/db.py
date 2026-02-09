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


def get_conn():
    db = get_database()
    conn = kuzu.Connection(db)
    try:
        yield conn
    finally:
        pass
