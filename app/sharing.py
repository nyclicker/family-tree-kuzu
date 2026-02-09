"""CRUD operations for share links and viewer access control."""
import uuid
from datetime import datetime, timezone
import kuzu


def create_share_link(conn: kuzu.Connection, dataset: str) -> dict:
    """Create a shareable token for a dataset."""
    token = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (s:ShareLink {id: $id, dataset: $ds, created_at: $ts})",
        {"id": token, "ds": dataset, "ts": now}
    )
    return {"token": token, "dataset": dataset, "created_at": now}


def list_share_links(conn: kuzu.Connection) -> list[dict]:
    """List all share links."""
    result = conn.execute(
        "MATCH (s:ShareLink) RETURN s.id, s.dataset, s.created_at ORDER BY s.created_at DESC"
    )
    links = []
    while result.has_next():
        row = result.get_next()
        links.append({"token": row[0], "dataset": row[1], "created_at": row[2]})
    return links


def get_share_link(conn: kuzu.Connection, token: str) -> dict | None:
    """Get a share link by token."""
    result = conn.execute(
        "MATCH (s:ShareLink) WHERE s.id = $id RETURN s.id, s.dataset, s.created_at",
        {"id": token}
    )
    if result.has_next():
        row = result.get_next()
        return {"token": row[0], "dataset": row[1], "created_at": row[2]}
    return None


def delete_share_link(conn: kuzu.Connection, token: str):
    """Delete a share link and all its access relationships."""
    conn.execute("MATCH (s:ShareLink) WHERE s.id = $id DETACH DELETE s", {"id": token})


def add_viewer(conn: kuzu.Connection, token: str, email: str, name: str = "") -> dict:
    """Add a viewer (by email) with access to a share link."""
    email = email.strip().lower()
    # Check if viewer already exists
    viewer = _get_viewer_by_email(conn, email)
    if not viewer:
        vid = str(uuid.uuid4())
        conn.execute(
            "CREATE (v:Viewer {id: $id, email: $email, name: $name})",
            {"id": vid, "email": email, "name": name or ""}
        )
        viewer = {"id": vid, "email": email, "name": name or ""}

    # Check if CAN_VIEW relationship already exists
    result = conn.execute(
        "MATCH (v:Viewer)-[:CAN_VIEW]->(s:ShareLink) "
        "WHERE v.id = $vid AND s.id = $sid RETURN count(*)",
        {"vid": viewer["id"], "sid": token}
    )
    if result.has_next() and result.get_next()[0] > 0:
        return viewer  # already has access

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "MATCH (v:Viewer), (s:ShareLink) WHERE v.id = $vid AND s.id = $sid "
        "CREATE (v)-[:CAN_VIEW {granted_at: $ts}]->(s)",
        {"vid": viewer["id"], "sid": token, "ts": now}
    )
    return viewer


def remove_viewer(conn: kuzu.Connection, token: str, viewer_id: str):
    """Remove a viewer's access to a share link."""
    conn.execute(
        "MATCH (v:Viewer)-[r:CAN_VIEW]->(s:ShareLink) "
        "WHERE v.id = $vid AND s.id = $sid DELETE r",
        {"vid": viewer_id, "sid": token}
    )


def list_viewers(conn: kuzu.Connection, token: str) -> list[dict]:
    """List all viewers with access to a share link."""
    result = conn.execute(
        "MATCH (v:Viewer)-[r:CAN_VIEW]->(s:ShareLink) WHERE s.id = $sid "
        "RETURN v.id, v.email, v.name, r.granted_at ORDER BY v.email",
        {"sid": token}
    )
    viewers = []
    while result.has_next():
        row = result.get_next()
        viewers.append({
            "id": row[0], "email": row[1], "name": row[2], "granted_at": row[3]
        })
    return viewers


def check_viewer_access(conn: kuzu.Connection, token: str, email: str) -> dict | None:
    """Check if a viewer (by email) has access to a share link. Returns viewer dict or None."""
    email = email.strip().lower()
    result = conn.execute(
        "MATCH (v:Viewer)-[:CAN_VIEW]->(s:ShareLink) "
        "WHERE s.id = $sid AND v.email = $email "
        "RETURN v.id, v.email, v.name",
        {"sid": token, "email": email}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "email": row[1], "name": row[2]}
    return None


def log_access(conn: kuzu.Connection, token: str, viewer_id: str, ip: str = ""):
    """Log that a viewer accessed a share link."""
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "MATCH (v:Viewer), (s:ShareLink) WHERE v.id = $vid AND s.id = $sid "
        "CREATE (v)-[:VIEWED {id: $id, viewed_at: $ts, ip: $ip}]->(s)",
        {"vid": viewer_id, "sid": token, "id": log_id, "ts": now, "ip": ip or ""}
    )


def get_access_log(conn: kuzu.Connection, token: str) -> list[dict]:
    """Get the access log for a share link."""
    result = conn.execute(
        "MATCH (v:Viewer)-[r:VIEWED]->(s:ShareLink) WHERE s.id = $sid "
        "RETURN v.email, v.name, r.viewed_at, r.ip ORDER BY r.viewed_at DESC",
        {"sid": token}
    )
    logs = []
    while result.has_next():
        row = result.get_next()
        logs.append({
            "email": row[0], "name": row[1], "viewed_at": row[2], "ip": row[3]
        })
    return logs


def _get_viewer_by_email(conn: kuzu.Connection, email: str) -> dict | None:
    result = conn.execute(
        "MATCH (v:Viewer) WHERE v.email = $email RETURN v.id, v.email, v.name",
        {"email": email}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "email": row[1], "name": row[2]}
    return None
