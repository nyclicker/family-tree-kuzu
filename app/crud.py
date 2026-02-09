"""CRUD operations using KuzuDB Cypher queries."""
import uuid
import kuzu

VALID_REL_TYPES = {"PARENT_OF", "SPOUSE_OF", "SIBLING_OF"}


def _person_from_row(row):
    return {
        "id": row[0],
        "display_name": row[1],
        "sex": row[2],
        "notes": row[3] if row[3] else None,
    }


def create_person(conn: kuzu.Connection, display_name: str, sex: str = "U",
                  notes: str | None = None, dataset: str = ""):
    pid = str(uuid.uuid4())
    conn.execute(
        "CREATE (p:Person {id: $id, display_name: $name, sex: $sex, notes: $notes, dataset: $ds})",
        {"id": pid, "name": display_name, "sex": sex, "notes": notes or "", "ds": dataset or ""}
    )
    return {"id": pid, "display_name": display_name, "sex": sex, "notes": notes}


def list_people(conn: kuzu.Connection):
    result = conn.execute(
        "MATCH (p:Person) RETURN p.id, p.display_name, p.sex, p.notes ORDER BY p.display_name"
    )
    people = []
    while result.has_next():
        people.append(_person_from_row(result.get_next()))
    return people


def get_person(conn: kuzu.Connection, person_id: str):
    result = conn.execute(
        "MATCH (p:Person) WHERE p.id = $id RETURN p.id, p.display_name, p.sex, p.notes",
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
                  sex: str, notes: str | None = None):
    if not get_person(conn, person_id):
        return None
    conn.execute(
        "MATCH (p:Person) WHERE p.id = $id "
        "SET p.display_name = $name, p.sex = $sex, p.notes = $notes",
        {"id": person_id, "name": display_name, "sex": sex, "notes": notes or ""}
    )
    return {"id": person_id, "display_name": display_name, "sex": sex, "notes": notes}


def delete_person(conn: kuzu.Connection, person_id: str):
    conn.execute("MATCH (p:Person) WHERE p.id = $id DETACH DELETE p", {"id": person_id})


def delete_relationship(conn: kuzu.Connection, rel_id: str):
    for rel_type in VALID_REL_TYPES:
        conn.execute(
            f"MATCH ()-[r:{rel_type}]->() WHERE r.id = $id DELETE r", {"id": rel_id}
        )


def find_person_by_name(conn: kuzu.Connection, display_name: str):
    result = conn.execute(
        "MATCH (p:Person) WHERE p.display_name = $name RETURN p.id, p.display_name, p.sex, p.notes",
        {"name": display_name}
    )
    if result.has_next():
        return _person_from_row(result.get_next())
    return None


def clear_all(conn: kuzu.Connection):
    conn.execute("MATCH (p:Person) DETACH DELETE p")
