"""UserGroup CRUD, membership management, and group-tree access grants."""
import uuid
from datetime import datetime, timezone
import kuzu


def create_group(conn: kuzu.Connection, name: str, description: str,
                 created_by: str) -> dict:
    gid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (g:UserGroup {id: $id, name: $name, descr: $desc, "
        "created_by: $cb, created_at: $ts})",
        {"id": gid, "name": name, "desc": description or "", "cb": created_by, "ts": now}
    )
    return {"id": gid, "name": name, "description": description or "",
            "created_by": created_by, "created_at": now}


def get_group(conn: kuzu.Connection, group_id: str) -> dict | None:
    result = conn.execute(
        "MATCH (g:UserGroup) WHERE g.id = $id "
        "RETURN g.id, g.name, g.descr, g.created_by, g.created_at",
        {"id": group_id}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "name": row[1], "description": row[2],
                "created_by": row[3], "created_at": row[4]}
    return None


def update_group(conn: kuzu.Connection, group_id: str, name: str, description: str):
    conn.execute(
        "MATCH (g:UserGroup) WHERE g.id = $id SET g.name = $name, g.descr = $desc",
        {"id": group_id, "name": name, "desc": description or ""}
    )


def delete_group(conn: kuzu.Connection, group_id: str):
    """Delete group and all its relationships (membership + tree grants)."""
    conn.execute(
        "MATCH (g:UserGroup) WHERE g.id = $id DETACH DELETE g",
        {"id": group_id}
    )


def list_user_groups(conn: kuzu.Connection, user_id: str) -> list[dict]:
    """List groups user created or belongs to."""
    groups = {}

    # Groups the user created
    result = conn.execute(
        "MATCH (g:UserGroup) WHERE g.created_by = $uid "
        "RETURN g.id, g.name, g.descr, g.created_by, g.created_at",
        {"uid": user_id}
    )
    while result.has_next():
        row = result.get_next()
        groups[row[0]] = {"id": row[0], "name": row[1], "description": row[2],
                          "created_by": row[3], "created_at": row[4], "is_member": False}

    # Groups the user is a member of
    result = conn.execute(
        "MATCH (u:User)-[:MEMBER_OF]->(g:UserGroup) WHERE u.id = $uid "
        "RETURN g.id, g.name, g.descr, g.created_by, g.created_at",
        {"uid": user_id}
    )
    while result.has_next():
        row = result.get_next()
        gid = row[0]
        if gid in groups:
            groups[gid]["is_member"] = True
        else:
            groups[gid] = {"id": gid, "name": row[1], "description": row[2],
                           "created_by": row[3], "created_at": row[4], "is_member": True}

    return sorted(groups.values(), key=lambda g: g["name"])


def list_all_groups(conn: kuzu.Connection) -> list[dict]:
    """List all groups (admin view)."""
    result = conn.execute(
        "MATCH (g:UserGroup) RETURN g.id, g.name, g.descr, g.created_by, g.created_at "
        "ORDER BY g.name"
    )
    groups = []
    while result.has_next():
        row = result.get_next()
        groups.append({"id": row[0], "name": row[1], "description": row[2],
                       "created_by": row[3], "created_at": row[4]})
    return groups


# ── Membership ──

def add_member(conn: kuzu.Connection, group_id: str, user_id: str):
    """Add a user to a group."""
    now = datetime.now(timezone.utc).isoformat()
    # Check if already a member
    result = conn.execute(
        "MATCH (u:User)-[:MEMBER_OF]->(g:UserGroup) WHERE u.id = $uid AND g.id = $gid "
        "RETURN count(*)",
        {"uid": user_id, "gid": group_id}
    )
    if result.has_next() and result.get_next()[0] > 0:
        return  # already a member
    conn.execute(
        "MATCH (u:User), (g:UserGroup) WHERE u.id = $uid AND g.id = $gid "
        "CREATE (u)-[:MEMBER_OF {added_at: $ts}]->(g)",
        {"uid": user_id, "gid": group_id, "ts": now}
    )


def remove_member(conn: kuzu.Connection, group_id: str, user_id: str):
    conn.execute(
        "MATCH (u:User)-[r:MEMBER_OF]->(g:UserGroup) WHERE u.id = $uid AND g.id = $gid "
        "DELETE r",
        {"uid": user_id, "gid": group_id}
    )


def list_members(conn: kuzu.Connection, group_id: str) -> list[dict]:
    result = conn.execute(
        "MATCH (u:User)-[r:MEMBER_OF]->(g:UserGroup) WHERE g.id = $gid "
        "RETURN u.id, u.email, u.display_name, r.added_at ORDER BY u.email",
        {"gid": group_id}
    )
    members = []
    while result.has_next():
        row = result.get_next()
        members.append({"id": row[0], "email": row[1], "display_name": row[2],
                        "added_at": row[3]})
    return members


def list_group_trees(conn: kuzu.Connection, group_id: str) -> list[dict]:
    """List trees this group can access."""
    result = conn.execute(
        "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE g.id = $gid "
        "RETURN t.id, t.name, r.role, r.granted_at ORDER BY t.name",
        {"gid": group_id}
    )
    trees = []
    while result.has_next():
        row = result.get_next()
        trees.append({"id": row[0], "name": row[1], "role": row[2], "granted_at": row[3]})
    return trees


def can_manage_group(conn: kuzu.Connection, group_id: str, user_id: str,
                     is_admin: bool) -> bool:
    """Check if user can manage this group (creator or admin)."""
    if is_admin:
        return True
    group = get_group(conn, group_id)
    if group and group["created_by"] == user_id:
        return True
    return False
