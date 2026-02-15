"""Tree change audit log."""
import uuid
from datetime import datetime, timezone
import kuzu


def record_change(conn: kuzu.Connection, tree_id: str, user_id: str, user_name: str,
                  action: str, entity_type: str, entity_id: str, details: str = ""):
    """Record a tree change for the audit log."""
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (c:TreeChange {id: $id, tree_id: $tid, user_id: $uid, user_name: $uname, "
        "action: $action, entity_type: $etype, entity_id: $eid, "
        "details: $details, created_at: $ts})",
        {"id": cid, "tid": tree_id, "uid": user_id, "uname": user_name,
         "action": action, "etype": entity_type, "eid": entity_id,
         "details": details, "ts": now}
    )
    return {"id": cid, "created_at": now}


def list_changes(conn: kuzu.Connection, tree_id: str, limit: int = 50, offset: int = 0):
    """List recent changes for a tree, newest first."""
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    result = conn.execute(
        f"MATCH (c:TreeChange) WHERE c.tree_id = $tid "
        f"RETURN c.id, c.tree_id, c.user_id, c.user_name, c.action, "
        f"c.entity_type, c.entity_id, c.details, c.created_at "
        f"ORDER BY c.created_at DESC "
        f"SKIP {offset} LIMIT {limit}",
        {"tid": tree_id}
    )
    changes = []
    while result.has_next():
        row = result.get_next()
        changes.append({
            "id": row[0],
            "tree_id": row[1],
            "user_id": row[2],
            "user_name": row[3],
            "action": row[4],
            "entity_type": row[5],
            "entity_id": row[6],
            "details": row[7],
            "created_at": row[8],
        })
    return changes
