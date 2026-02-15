"""FamilyTree CRUD, ownership, and permission checking."""
import uuid
from datetime import datetime, timezone
import kuzu


ROLE_HIERARCHY = {"owner": 3, "editor": 2, "viewer": 1, "none": 0}


def create_tree(conn: kuzu.Connection, name: str, owner_id: str) -> dict:
    """Create a new FamilyTree and set the user as owner."""
    tid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (t:FamilyTree {id: $id, name: $name, created_at: $ts})",
        {"id": tid, "name": name, "ts": now}
    )
    conn.execute(
        "MATCH (u:User), (t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "CREATE (u)-[:OWNS]->(t)",
        {"uid": owner_id, "tid": tid}
    )
    return {"id": tid, "name": name, "created_at": now, "role": "owner"}


def get_tree(conn: kuzu.Connection, tree_id: str) -> dict | None:
    result = conn.execute(
        "MATCH (t:FamilyTree) WHERE t.id = $id RETURN t.id, t.name, t.created_at",
        {"id": tree_id}
    )
    if result.has_next():
        row = result.get_next()
        return {"id": row[0], "name": row[1], "created_at": row[2]}
    return None


def rename_tree(conn: kuzu.Connection, tree_id: str, name: str):
    conn.execute(
        "MATCH (t:FamilyTree) WHERE t.id = $id SET t.name = $name",
        {"id": tree_id, "name": name}
    )


def delete_tree(conn: kuzu.Connection, tree_id: str):
    """Delete a tree, all its people, comments, share links, and access relationships."""
    # Delete all comments in this tree
    conn.execute(
        "MATCH (c:PersonComment) WHERE c.tree_id = $tid DELETE c",
        {"tid": tree_id}
    )
    # Delete all people in this tree
    conn.execute(
        "MATCH (p:Person) WHERE p.tree_id = $tid DETACH DELETE p",
        {"tid": tree_id}
    )
    # Delete all share links for this tree
    conn.execute(
        "MATCH (s:ShareLink) WHERE s.tree_id = $tid DETACH DELETE s",
        {"tid": tree_id}
    )
    # Delete the tree node (cascades OWNS, CAN_ACCESS, GROUP_CAN_ACCESS edges)
    conn.execute(
        "MATCH (t:FamilyTree) WHERE t.id = $tid DETACH DELETE t",
        {"tid": tree_id}
    )


def list_user_trees(conn: kuzu.Connection, user_id: str) -> list[dict]:
    """List all trees a user can access (owned + direct + group grants)."""
    trees = {}

    # 1. Owned trees
    result = conn.execute(
        "MATCH (u:User)-[:OWNS]->(t:FamilyTree) WHERE u.id = $uid "
        "RETURN t.id, t.name, t.created_at",
        {"uid": user_id}
    )
    while result.has_next():
        row = result.get_next()
        trees[row[0]] = {"id": row[0], "name": row[1], "created_at": row[2], "role": "owner"}

    # 2. Direct CAN_ACCESS
    result = conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid "
        "RETURN t.id, t.name, t.created_at, r.role",
        {"uid": user_id}
    )
    while result.has_next():
        row = result.get_next()
        tid = row[0]
        if tid not in trees or ROLE_HIERARCHY.get(row[3], 0) > ROLE_HIERARCHY.get(trees[tid]["role"], 0):
            trees[tid] = {"id": tid, "name": row[1], "created_at": row[2], "role": row[3]}

    # 3. Group grants
    result = conn.execute(
        "MATCH (u:User)-[:MEMBER_OF]->(g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) "
        "WHERE u.id = $uid RETURN t.id, t.name, t.created_at, r.role",
        {"uid": user_id}
    )
    while result.has_next():
        row = result.get_next()
        tid = row[0]
        role = row[3]
        if tid not in trees or ROLE_HIERARCHY.get(role, 0) > ROLE_HIERARCHY.get(trees[tid]["role"], 0):
            trees[tid] = {"id": tid, "name": row[1], "created_at": row[2], "role": role}

    return sorted(trees.values(), key=lambda t: t["name"])


def get_user_role(conn: kuzu.Connection, user_id: str, tree_id: str) -> str:
    """Resolve the effective role of a user for a tree.
    Returns 'owner', 'editor', 'viewer', or 'none'."""

    # 1. Check ownership
    result = conn.execute(
        "MATCH (u:User)-[:OWNS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "RETURN count(*)",
        {"uid": user_id, "tid": tree_id}
    )
    if result.has_next() and result.get_next()[0] > 0:
        return "owner"

    best = "none"

    # 2. Direct CAN_ACCESS
    result = conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "RETURN r.role",
        {"uid": user_id, "tid": tree_id}
    )
    if result.has_next():
        role = result.get_next()[0]
        if ROLE_HIERARCHY.get(role, 0) > ROLE_HIERARCHY.get(best, 0):
            best = role

    # 3. Group grants
    result = conn.execute(
        "MATCH (u:User)-[:MEMBER_OF]->(g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) "
        "WHERE u.id = $uid AND t.id = $tid RETURN r.role",
        {"uid": user_id, "tid": tree_id}
    )
    while result.has_next():
        role = result.get_next()[0]
        if ROLE_HIERARCHY.get(role, 0) > ROLE_HIERARCHY.get(best, 0):
            best = role

    return best


def require_role(conn: kuzu.Connection, user_id: str, tree_id: str, min_role: str):
    """Check that user has at least min_role on tree. Raises HTTPException otherwise."""
    from fastapi import HTTPException
    role = get_user_role(conn, user_id, tree_id)
    if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(min_role, 0):
        if role == "none":
            raise HTTPException(404, "Tree not found")
        raise HTTPException(403, f"Requires {min_role} access")
    return role


# ── Tree member (direct access) management ──

def list_tree_members(conn: kuzu.Connection, tree_id: str) -> dict:
    """List owner, direct user grants, and group grants for a tree."""
    # Owner
    result = conn.execute(
        "MATCH (u:User)-[:OWNS]->(t:FamilyTree) WHERE t.id = $tid "
        "RETURN u.id, u.email, u.display_name",
        {"tid": tree_id}
    )
    owner = None
    if result.has_next():
        row = result.get_next()
        owner = {"id": row[0], "email": row[1], "display_name": row[2], "role": "owner"}

    # Direct users
    users = []
    result = conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE t.id = $tid "
        "RETURN u.id, u.email, u.display_name, r.role, r.granted_at ORDER BY u.email",
        {"tid": tree_id}
    )
    while result.has_next():
        row = result.get_next()
        users.append({"id": row[0], "email": row[1], "display_name": row[2],
                       "role": row[3], "granted_at": row[4]})

    # Groups
    groups = []
    result = conn.execute(
        "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE t.id = $tid "
        "RETURN g.id, g.name, r.role, r.granted_at ORDER BY g.name",
        {"tid": tree_id}
    )
    while result.has_next():
        row = result.get_next()
        groups.append({"id": row[0], "name": row[1], "role": row[2], "granted_at": row[3]})

    return {"owner": owner, "users": users, "groups": groups}


def grant_user_access(conn: kuzu.Connection, tree_id: str, user_id: str, role: str):
    """Grant or update direct user access to a tree."""
    now = datetime.now(timezone.utc).isoformat()
    # Check if access already exists
    result = conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "RETURN count(*)",
        {"uid": user_id, "tid": tree_id}
    )
    if result.has_next() and result.get_next()[0] > 0:
        # Update existing
        conn.execute(
            "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
            "SET r.role = $role, r.granted_at = $ts",
            {"uid": user_id, "tid": tree_id, "role": role, "ts": now}
        )
    else:
        conn.execute(
            "MATCH (u:User), (t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
            "CREATE (u)-[:CAN_ACCESS {role: $role, granted_at: $ts}]->(t)",
            {"uid": user_id, "tid": tree_id, "role": role, "ts": now}
        )


def update_user_access(conn: kuzu.Connection, tree_id: str, user_id: str, role: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "SET r.role = $role, r.granted_at = $ts",
        {"uid": user_id, "tid": tree_id, "role": role, "ts": now}
    )


def revoke_user_access(conn: kuzu.Connection, tree_id: str, user_id: str):
    conn.execute(
        "MATCH (u:User)-[r:CAN_ACCESS]->(t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
        "DELETE r",
        {"uid": user_id, "tid": tree_id}
    )


def grant_group_access(conn: kuzu.Connection, tree_id: str, group_id: str, role: str):
    now = datetime.now(timezone.utc).isoformat()
    # Check if access already exists
    result = conn.execute(
        "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE g.id = $gid AND t.id = $tid "
        "RETURN count(*)",
        {"gid": group_id, "tid": tree_id}
    )
    if result.has_next() and result.get_next()[0] > 0:
        conn.execute(
            "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE g.id = $gid AND t.id = $tid "
            "SET r.role = $role, r.granted_at = $ts",
            {"gid": group_id, "tid": tree_id, "role": role, "ts": now}
        )
    else:
        conn.execute(
            "MATCH (g:UserGroup), (t:FamilyTree) WHERE g.id = $gid AND t.id = $tid "
            "CREATE (g)-[:GROUP_CAN_ACCESS {role: $role, granted_at: $ts}]->(t)",
            {"gid": group_id, "tid": tree_id, "role": role, "ts": now}
        )


def update_group_access(conn: kuzu.Connection, tree_id: str, group_id: str, role: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE g.id = $gid AND t.id = $tid "
        "SET r.role = $role, r.granted_at = $ts",
        {"gid": group_id, "tid": tree_id, "role": role, "ts": now}
    )


def revoke_group_access(conn: kuzu.Connection, tree_id: str, group_id: str):
    conn.execute(
        "MATCH (g:UserGroup)-[r:GROUP_CAN_ACCESS]->(t:FamilyTree) WHERE g.id = $gid AND t.id = $tid "
        "DELETE r",
        {"gid": group_id, "tid": tree_id}
    )


def get_tree_owner_id(conn: kuzu.Connection, tree_id: str) -> str | None:
    result = conn.execute(
        "MATCH (u:User)-[:OWNS]->(t:FamilyTree) WHERE t.id = $tid RETURN u.id",
        {"tid": tree_id}
    )
    if result.has_next():
        return result.get_next()[0]
    return None
