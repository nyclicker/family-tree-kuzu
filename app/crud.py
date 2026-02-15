"""CRUD operations using KuzuDB Cypher queries."""
import uuid
from datetime import datetime, timezone
import kuzu

VALID_REL_TYPES = {"PARENT_OF", "SPOUSE_OF"}


def _person_from_row(row):
    return {
        "id": row[0],
        "display_name": row[1],
        "sex": row[2],
        "notes": row[3] if row[3] else None,
        "birth_date": row[4] if len(row) > 4 and row[4] else None,
        "death_date": row[5] if len(row) > 5 and row[5] else None,
        "is_deceased": row[6] if len(row) > 6 else None,
    }


_PERSON_RETURN = "p.id, p.display_name, p.sex, p.notes, p.birth_date, p.death_date, p.is_deceased"


def create_person(conn: kuzu.Connection, display_name: str, sex: str = "U",
                  notes: str | None = None, dataset: str = "", tree_id: str = "",
                  birth_date: str | None = None, death_date: str | None = None,
                  is_deceased: bool | None = None):
    pid = str(uuid.uuid4())
    # Auto-set is_deceased if death_date provided
    if death_date and is_deceased is None:
        is_deceased = True
    conn.execute(
        "CREATE (p:Person {id: $id, display_name: $name, sex: $sex, notes: $notes, "
        "dataset: $ds, tree_id: $tid, birth_date: $bd, death_date: $dd, is_deceased: $dec})",
        {"id": pid, "name": display_name, "sex": sex, "notes": notes or "",
         "ds": dataset or "", "tid": tree_id or "",
         "bd": birth_date or "", "dd": death_date or "", "dec": bool(is_deceased)}
    )
    return {"id": pid, "display_name": display_name, "sex": sex, "notes": notes,
            "birth_date": birth_date, "death_date": death_date, "is_deceased": is_deceased or False}


def list_people(conn: kuzu.Connection, tree_id: str = ""):
    if tree_id:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.tree_id = $tid "
            f"RETURN {_PERSON_RETURN} ORDER BY p.display_name",
            {"tid": tree_id}
        )
    else:
        result = conn.execute(
            f"MATCH (p:Person) RETURN {_PERSON_RETURN} ORDER BY p.display_name"
        )
    people = []
    while result.has_next():
        people.append(_person_from_row(result.get_next()))
    return people


def get_person(conn: kuzu.Connection, person_id: str, tree_id: str = ""):
    if tree_id:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.id = $id AND p.tree_id = $tid "
            f"RETURN {_PERSON_RETURN}",
            {"id": person_id, "tid": tree_id}
        )
    else:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.id = $id RETURN {_PERSON_RETURN}",
            {"id": person_id}
        )
    if result.has_next():
        return _person_from_row(result.get_next())
    return None


def create_relationship(conn: kuzu.Connection, from_id: str, to_id: str, rel_type: str):
    if rel_type not in VALID_REL_TYPES:
        raise ValueError(f"Invalid relationship type: {rel_type}")
    rid = str(uuid.uuid4())
    conn.execute(
        f"MATCH (a:Person), (b:Person) WHERE a.id = $fid AND b.id = $tid "
        f"CREATE (a)-[:{rel_type} {{id: $id}}]->(b)",
        {"fid": from_id, "tid": to_id, "id": rid}
    )
    return {"id": rid, "from_person_id": from_id, "to_person_id": to_id, "type": rel_type}


def update_person(conn: kuzu.Connection, person_id: str, display_name: str,
                  sex: str, notes: str | None = None, tree_id: str = "",
                  birth_date: str | None = None, death_date: str | None = None,
                  is_deceased: bool | None = None):
    if not get_person(conn, person_id, tree_id):
        return None
    # Auto-set is_deceased if death_date provided
    if death_date and is_deceased is None:
        is_deceased = True
    conn.execute(
        "MATCH (p:Person) WHERE p.id = $id "
        "SET p.display_name = $name, p.sex = $sex, p.notes = $notes, "
        "p.birth_date = $bd, p.death_date = $dd, p.is_deceased = $dec",
        {"id": person_id, "name": display_name, "sex": sex, "notes": notes or "",
         "bd": birth_date or "", "dd": death_date or "", "dec": bool(is_deceased)}
    )
    return {"id": person_id, "display_name": display_name, "sex": sex, "notes": notes,
            "birth_date": birth_date, "death_date": death_date, "is_deceased": is_deceased or False}


def delete_person(conn: kuzu.Connection, person_id: str, tree_id: str = ""):
    if tree_id:
        # Verify person belongs to tree before deleting
        if not get_person(conn, person_id, tree_id):
            return
    # Cascade-delete comments for this person
    conn.execute("MATCH (c:PersonComment) WHERE c.person_id = $pid DELETE c", {"pid": person_id})
    conn.execute("MATCH (p:Person) WHERE p.id = $id DETACH DELETE p", {"id": person_id})


def delete_relationship(conn: kuzu.Connection, rel_id: str):
    # Include SIBLING_OF for backward compat cleanup of legacy edges
    for rel_type in ["PARENT_OF", "SPOUSE_OF", "SIBLING_OF"]:
        try:
            conn.execute(
                f"MATCH ()-[r:{rel_type}]->() WHERE r.id = $id DELETE r", {"id": rel_id}
            )
        except Exception:
            pass


def find_person_by_name(conn: kuzu.Connection, display_name: str, tree_id: str = ""):
    if tree_id:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.display_name = $name AND p.tree_id = $tid "
            f"RETURN {_PERSON_RETURN}",
            {"name": display_name, "tid": tree_id}
        )
    else:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.display_name = $name RETURN {_PERSON_RETURN}",
            {"name": display_name}
        )
    if result.has_next():
        return _person_from_row(result.get_next())
    return None


def get_children(conn: kuzu.Connection, person_id: str):
    """Get all children of a person (via outgoing PARENT_OF edges)."""
    result = conn.execute(
        f"MATCH (p:Person)-[:PARENT_OF]->(c:Person) WHERE p.id = $id "
        f"RETURN {_PERSON_RETURN.replace('p.', 'c.')}",
        {"id": person_id}
    )
    children = []
    while result.has_next():
        children.append(_person_from_row(result.get_next()))
    return children


def get_parents(conn: kuzu.Connection, person_id: str):
    """Get all parents of a person (incoming PARENT_OF edges)."""
    result = conn.execute(
        "MATCH (parent:Person)-[:PARENT_OF]->(child:Person) WHERE child.id = $id "
        "RETURN parent.id, parent.display_name, parent.sex, parent.notes, "
        "parent.birth_date, parent.death_date, parent.is_deceased",
        {"id": person_id}
    )
    parents = []
    while result.has_next():
        parents.append(_person_from_row(result.get_next()))
    return parents


def delete_parent_relationship(conn: kuzu.Connection, parent_id: str, child_id: str):
    """Delete a specific PARENT_OF edge between parent and child."""
    conn.execute(
        "MATCH (a:Person)-[r:PARENT_OF]->(b:Person) "
        "WHERE a.id = $pid AND b.id = $cid DELETE r",
        {"pid": parent_id, "cid": child_id}
    )


def _edge_exists(conn: kuzu.Connection, from_id: str, to_id: str, rel_type: str) -> bool:
    """Check if an edge exists (checks reverse for symmetric relations)."""
    result = conn.execute(
        f"MATCH (a:Person)-[:{rel_type}]->(b:Person) "
        f"WHERE a.id = $fid AND b.id = $tid RETURN count(*)",
        {"fid": from_id, "tid": to_id}
    )
    if result.has_next() and result.get_next()[0] > 0:
        return True
    if rel_type in ("SPOUSE_OF", "SIBLING_OF"):
        result = conn.execute(
            f"MATCH (a:Person)-[:{rel_type}]->(b:Person) "
            f"WHERE a.id = $fid AND b.id = $tid RETURN count(*)",
            {"fid": to_id, "tid": from_id}
        )
        if result.has_next() and result.get_next()[0] > 0:
            return True
    return False


def merge_person_into(conn: kuzu.Connection, keep_id: str, remove_id: str):
    """Merge remove_id into keep_id: transfer all edges, update properties, delete remove_id."""
    # Update keep's properties if remove has better data
    keep = get_person(conn, keep_id)
    remove = get_person(conn, remove_id)
    if keep and remove:
        changed = False
        sex = keep["sex"]
        notes = keep.get("notes") or ""
        birth_date = keep.get("birth_date") or ""
        death_date = keep.get("death_date") or ""
        is_deceased = keep.get("is_deceased") or False
        if sex == "U" and remove["sex"] != "U":
            sex = remove["sex"]
            changed = True
        if not notes and remove.get("notes"):
            notes = remove["notes"]
            changed = True
        if not birth_date and remove.get("birth_date"):
            birth_date = remove["birth_date"]
            changed = True
        if not death_date and remove.get("death_date"):
            death_date = remove["death_date"]
            changed = True
        if not is_deceased and remove.get("is_deceased"):
            is_deceased = True
            changed = True
        if changed:
            conn.execute(
                "MATCH (p:Person) WHERE p.id = $id "
                "SET p.sex = $sex, p.notes = $notes, "
                "p.birth_date = $bd, p.death_date = $dd, p.is_deceased = $dec",
                {"id": keep_id, "sex": sex, "notes": notes,
                 "bd": birth_date, "dd": death_date, "dec": bool(is_deceased)}
            )

    # Transfer outgoing edges from remove to keep
    for rel_type in VALID_REL_TYPES:
        result = conn.execute(
            f"MATCH (a:Person)-[:{rel_type}]->(b:Person) WHERE a.id = $id RETURN b.id",
            {"id": remove_id}
        )
        targets = []
        while result.has_next():
            targets.append(result.get_next()[0])
        for target_id in targets:
            if target_id != keep_id and not _edge_exists(conn, keep_id, target_id, rel_type):
                create_relationship(conn, keep_id, target_id, rel_type)

    # Transfer incoming edges from remove to keep
    for rel_type in VALID_REL_TYPES:
        result = conn.execute(
            f"MATCH (a:Person)-[:{rel_type}]->(b:Person) WHERE b.id = $id RETURN a.id",
            {"id": remove_id}
        )
        sources = []
        while result.has_next():
            sources.append(result.get_next()[0])
        for source_id in sources:
            if source_id != keep_id and not _edge_exists(conn, source_id, keep_id, rel_type):
                create_relationship(conn, source_id, keep_id, rel_type)

    # Delete the merged person and all its edges
    delete_person(conn, remove_id)


def merge_spouse_children(conn: kuzu.Connection, spouse_a_id: str, spouse_b_id: str):
    """After linking spouses, merge common children and share all children between both parents.

    1. Children with matching names under both parents -> merge into one node
    2. Children only under A -> also become children of B
    3. Children only under B -> also become children of A

    Returns dict with merged, adopted_by_a, adopted_by_b lists."""
    children_a = get_children(conn, spouse_a_id)
    children_b = get_children(conn, spouse_b_id)

    a_by_name = {c["display_name"]: c for c in children_a}
    b_by_name = {c["display_name"]: c for c in children_b}

    common_names = set(a_by_name.keys()) & set(b_by_name.keys())
    a_only = set(a_by_name.keys()) - common_names
    b_only = set(b_by_name.keys()) - common_names

    # 1. Merge children with the same name
    merged = []
    for name in sorted(common_names):
        keep = a_by_name[name]
        remove = b_by_name[name]
        if keep["id"] == remove["id"]:
            continue  # already the same node
        merge_person_into(conn, keep["id"], remove["id"])
        merged.append({"name": name, "kept_id": keep["id"], "removed_id": remove["id"]})

    # 2. Children only under A -> add B as parent too
    shared_with_b = []
    for name in sorted(a_only):
        child = a_by_name[name]
        if not _edge_exists(conn, spouse_b_id, child["id"], "PARENT_OF"):
            create_relationship(conn, spouse_b_id, child["id"], "PARENT_OF")
            shared_with_b.append(name)

    # 3. Children only under B -> add A as parent too
    shared_with_a = []
    for name in sorted(b_only):
        child = b_by_name[name]
        if not _edge_exists(conn, spouse_a_id, child["id"], "PARENT_OF"):
            create_relationship(conn, spouse_a_id, child["id"], "PARENT_OF")
            shared_with_a.append(name)

    return {
        "merged": merged,
        "shared_with_a": shared_with_a,
        "shared_with_b": shared_with_b,
    }


def count_parents(conn: kuzu.Connection, person_id: str) -> int:
    """Count how many parents a person has (incoming PARENT_OF edges)."""
    result = conn.execute(
        "MATCH (parent:Person)-[:PARENT_OF]->(child:Person) WHERE child.id = $id RETURN count(*)",
        {"id": person_id}
    )
    if result.has_next():
        return result.get_next()[0]
    return 0


def count_spouses(conn: kuzu.Connection, person_id: str) -> int:
    """Count how many spouses a person has (SPOUSE_OF in either direction)."""
    result = conn.execute(
        "MATCH (a:Person)-[:SPOUSE_OF]->(b:Person) "
        "WHERE a.id = $id OR b.id = $id RETURN count(*)",
        {"id": person_id}
    )
    if result.has_next():
        return result.get_next()[0]
    return 0


def clear_all(conn: kuzu.Connection, tree_id: str = ""):
    if tree_id:
        conn.execute("MATCH (c:PersonComment) WHERE c.tree_id = $tid DELETE c", {"tid": tree_id})
        conn.execute("MATCH (p:Person) WHERE p.tree_id = $tid DETACH DELETE p", {"tid": tree_id})
    else:
        conn.execute("MATCH (c:PersonComment) DELETE c")
        conn.execute("MATCH (p:Person) DETACH DELETE p")


# ── Comment CRUD ──

def _comment_from_row(row):
    return {
        "id": row[0],
        "person_id": row[1],
        "author_id": row[2],
        "author_name": row[3],
        "content": row[4],
        "created_at": row[5],
    }


def create_comment(conn: kuzu.Connection, person_id: str, tree_id: str,
                   author_id: str, author_name: str, content: str):
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "CREATE (c:PersonComment {id: $id, person_id: $pid, tree_id: $tid, "
        "author_id: $aid, author_name: $aname, content: $content, created_at: $ts})",
        {"id": cid, "pid": person_id, "tid": tree_id,
         "aid": author_id, "aname": author_name, "content": content, "ts": now}
    )
    return {"id": cid, "person_id": person_id, "author_id": author_id,
            "author_name": author_name, "content": content, "created_at": now}


def list_comments(conn: kuzu.Connection, person_id: str, tree_id: str):
    result = conn.execute(
        "MATCH (c:PersonComment) WHERE c.person_id = $pid AND c.tree_id = $tid "
        "RETURN c.id, c.person_id, c.author_id, c.author_name, c.content, c.created_at "
        "ORDER BY c.created_at",
        {"pid": person_id, "tid": tree_id}
    )
    comments = []
    while result.has_next():
        comments.append(_comment_from_row(result.get_next()))
    return comments


def get_comment(conn: kuzu.Connection, comment_id: str):
    result = conn.execute(
        "MATCH (c:PersonComment) WHERE c.id = $id "
        "RETURN c.id, c.person_id, c.author_id, c.author_name, c.content, c.created_at",
        {"id": comment_id}
    )
    if result.has_next():
        return _comment_from_row(result.get_next())
    return None


def delete_comment(conn: kuzu.Connection, comment_id: str):
    conn.execute("MATCH (c:PersonComment) WHERE c.id = $id DELETE c", {"id": comment_id})
