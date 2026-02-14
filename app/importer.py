"""Smart CSV/TXT/DB importer with duplicate name resolution — KuzuDB version."""

import csv
import io
import sqlite3
import tempfile
import os
from collections import defaultdict
import kuzu
from . import crud


def clean_name(raw: str) -> str:
    """Normalize raw name from CSV. Preserve \\n as real newline for two-line display."""
    return raw.replace("\\n", "\n").strip()


def parse_csv_rows(text: str) -> list[dict]:
    """Parse legacy CSV text into a list of row dicts."""
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # skip header
    rows = []
    for i, row in enumerate(reader, start=2):
        if not row or row[0].strip().startswith("#"):
            continue
        raw_p1 = row[0].strip() if len(row) > 0 else ""
        relation = row[1].strip() if len(row) > 1 else ""
        raw_p2 = row[2].strip() if len(row) > 2 else ""
        gender = row[3].strip() if len(row) > 3 else "U"
        details = row[4].strip() if len(row) > 4 else ""
        if not gender or gender.lower() in ("", "nan", "none"):
            gender = "U"
        if details.lower() in ("nan", "none", ""):
            details = ""
        if not raw_p1:
            continue
        rows.append({
            "line": i, "raw_p1": raw_p1, "relation": relation,
            "raw_p2": raw_p2, "gender": gender, "details": details,
        })
    return rows


def detect_and_resolve_duplicates(rows: list[dict]):
    """Detect duplicate names with different parents. Auto-resolve by appending parent name."""
    name_parents = defaultdict(list)
    for row in rows:
        name = clean_name(row["raw_p1"])
        parent = clean_name(row["raw_p2"]) if row["raw_p2"] else None
        name_parents[name].append({"row": row, "parent": parent})

    ambiguous_names = set()
    for name, entries in name_parents.items():
        parents = set(e["parent"] for e in entries if e["parent"])
        if len(parents) > 1:
            ambiguous_names.add(name)

    rename_map = {}
    auto_fixes = []
    for name in ambiguous_names:
        for entry in name_parents[name]:
            parent = entry["parent"]
            if parent:
                resolved = f"{name} ({parent})"
                rename_map[(name, parent)] = resolved
                auto_fixes.append({
                    "line": entry["row"]["line"], "type": "auto_renamed",
                    "message": f'Duplicate name "{name}" disambiguated to "{resolved}" (parent: {parent})',
                    "original": name, "resolved": resolved,
                })

    ambiguous_versions = {}
    for name in ambiguous_names:
        versions = {}
        for entry in name_parents[name]:
            parent = entry["parent"]
            if parent:
                resolved = rename_map.get((name, parent), name)
                versions[parent] = {"resolved": resolved, "line": entry["row"]["line"]}
        ambiguous_versions[name] = versions

    return rename_map, ambiguous_versions, auto_fixes, []


def import_csv_text(conn: kuzu.Connection, text: str, dataset: str = "",
                    clear_first: bool = True, tree_id: str = "") -> dict:
    """Import legacy CSV text with smart duplicate resolution."""
    rows = parse_csv_rows(text)
    if not rows:
        return {"people": 0, "relationships": 0, "auto_fixes": [],
                "errors": [{"line": 0, "type": "empty", "message": "No data rows found"}]}

    if clear_first:
        crud.clear_all(conn, tree_id=tree_id)

    rename_map, ambiguous_versions, auto_fixes, errors = detect_and_resolve_duplicates(rows)
    person_registry = {}  # display_name -> {"id": ..., "sex": ..., "notes": ...}
    created_edges = set()  # (from_id, to_id, rel_type) to prevent duplicates
    rel_count = 0

    def resolve_name(raw_name, parent_raw=None):
        name = clean_name(raw_name)
        parent_name = clean_name(parent_raw) if parent_raw else None
        if parent_name and (name, parent_name) in rename_map:
            return rename_map[(name, parent_name)]
        return name

    def get_or_create(display_name, sex="U", notes=None):
        if display_name in person_registry:
            p = person_registry[display_name]
            changed = False
            if sex != "U" and p["sex"] == "U":
                p["sex"] = sex
                changed = True
            if notes and not p["notes"]:
                p["notes"] = notes
                changed = True
            if changed:
                conn.execute(
                    "MATCH (p:Person) WHERE p.id = $id SET p.sex = $sex, p.notes = $notes",
                    {"id": p["id"], "sex": p["sex"], "notes": p["notes"] or ""}
                )
            return p
        # Cross-file dedup: check if person already exists in DB from a previous file
        existing = crud.find_person_by_name(conn, display_name, tree_id=tree_id)
        if existing:
            person_registry[display_name] = existing
            return existing
        p = crud.create_person(conn, display_name, sex, notes, dataset, tree_id=tree_id)
        person_registry[display_name] = p
        return p

    def resolve_p2_reference(raw_p2, child_display_name, current_line=0):
        p2_name = clean_name(raw_p2)
        if p2_name not in ambiguous_versions:
            return p2_name, None
        versions = ambiguous_versions[p2_name]
        existing = [v for v in versions.values() if v["resolved"] in person_registry]
        if len(existing) == 1:
            return existing[0]["resolved"], None
        if len(existing) > 1 and current_line > 0:
            closest = min(existing, key=lambda v: abs(v["line"] - current_line))
            return closest["resolved"], None
        if p2_name in person_registry:
            return p2_name, None
        all_resolved = [v["resolved"] for v in versions.values()]
        return p2_name, {
            "line": 0, "type": "ambiguous_parent",
            "message": f'Parent "{p2_name}" for child "{child_display_name}" is ambiguous.',
            "parent_name": p2_name, "child_name": child_display_name,
            "candidates": all_resolved,
        }

    # Pass 1: Create all people (p1 entries)
    for row in rows:
        # For "Child" relation, p2 is the parent (used for disambiguation)
        parent_raw = row["raw_p2"] if row["relation"] == "Child" else None
        display_name = resolve_name(row["raw_p1"], parent_raw)
        get_or_create(display_name, row["gender"], row["details"] or None)

    # Pass 2: Ensure all p2 references exist
    for row in rows:
        if row["raw_p2"]:
            p2_name = clean_name(row["raw_p2"])
            if p2_name not in person_registry:
                found = False
                if p2_name in ambiguous_versions:
                    for v in ambiguous_versions[p2_name].values():
                        if v["resolved"] in person_registry:
                            found = True
                            break
                if not found:
                    get_or_create(p2_name)

    def add_edge(from_id, to_id, rel_type, line):
        """Create edge if it doesn't already exist (prevents duplicates from redundant records)."""
        nonlocal rel_count
        edge_key = (from_id, to_id, rel_type)
        # Also check reverse for spouse (A spouse B == B spouse A)
        rev_key = (to_id, from_id, rel_type) if rel_type == "SPOUSE_OF" else None
        if edge_key in created_edges or (rev_key and rev_key in created_edges):
            auto_fixes.append({
                "line": line, "type": "skip_duplicate_edge",
                "message": f"Skipped duplicate {rel_type} edge (already exists)",
            })
            return
        try:
            crud.create_relationship(conn, from_id, to_id, rel_type)
            created_edges.add(edge_key)
            rel_count += 1
        except Exception as e:
            errors.append({"line": line, "type": "rel_error", "message": str(e)})

    # Pass 3: Create relationships
    for row in rows:
        p1_display = resolve_name(
            row["raw_p1"], row["raw_p2"] if row["relation"] == "Child" else None
        )
        if row["relation"] == "Child" and row["raw_p2"]:
            p2_display, err = resolve_p2_reference(row["raw_p2"], p1_display, row["line"])
            if err:
                err["line"] = row["line"]
                errors.append(err)
            p1 = person_registry.get(p1_display)
            p2 = person_registry.get(p2_display)
            if p1 and p2:
                add_edge(p2["id"], p1["id"], "PARENT_OF", row["line"])
            else:
                missing = p1_display if not p1 else p2_display
                errors.append({
                    "line": row["line"], "type": "missing_person",
                    "message": f'Could not find "{missing}" for relationship',
                })
        elif row["relation"] == "Parent" and row["raw_p2"]:
            p2_display, err = resolve_p2_reference(row["raw_p2"], p1_display, row["line"])
            if err:
                err["line"] = row["line"]
                errors.append(err)
            p1 = person_registry.get(p1_display)
            p2 = person_registry.get(p2_display)
            if p1 and p2:
                add_edge(p1["id"], p2["id"], "PARENT_OF", row["line"])
            else:
                missing = p1_display if not p1 else p2_display
                errors.append({
                    "line": row["line"], "type": "missing_person",
                    "message": f'Could not find "{missing}" for relationship',
                })
        elif row["relation"] == "Spouse" and row["raw_p2"]:
            p2_display, err = resolve_p2_reference(row["raw_p2"], p1_display, row["line"])
            if err:
                err["line"] = row["line"]
                errors.append(err)
            p1 = person_registry.get(p1_display)
            p2 = person_registry.get(p2_display)
            if p1 and p2:
                add_edge(p1["id"], p2["id"], "SPOUSE_OF", row["line"])
        elif row["relation"] == "Sibling" and row["raw_p2"]:
            # Sibling = share the same parents. Find p2's parents and add them as parents of p1.
            p2_display, err = resolve_p2_reference(row["raw_p2"], p1_display, row["line"])
            if err:
                err["line"] = row["line"]
                errors.append(err)
            p1 = person_registry.get(p1_display)
            p2 = person_registry.get(p2_display)
            if p1 and p2:
                # Find p2's parents and make them parents of p1 too
                p2_parents = crud.get_parents(conn, p2["id"])
                if p2_parents:
                    for parent in p2_parents:
                        add_edge(parent["id"], p1["id"], "PARENT_OF", row["line"])
                else:
                    # p2 has no parents yet — find p1's parents and make them parents of p2
                    p1_parents = crud.get_parents(conn, p1["id"])
                    if p1_parents:
                        for parent in p1_parents:
                            add_edge(parent["id"], p2["id"], "PARENT_OF", row["line"])
                    else:
                        auto_fixes.append({
                            "line": row["line"], "type": "sibling_no_parent",
                            "message": f'Sibling "{p1_display}" and "{p2_display}" have no parents — cannot link as siblings',
                        })
        elif row["relation"] == "Earliest Ancestor":
            pass
        elif row["relation"] and row["relation"] not in ("Child", "Parent", "Spouse", "Sibling", "Earliest Ancestor"):
            errors.append({
                "line": row["line"], "type": "unknown_relation",
                "message": f'Unknown relation type "{row["relation"]}"',
            })

    total_people = len(crud.list_people(conn, tree_id=tree_id))
    return {
        "people": total_people, "relationships": rel_count,
        "auto_fixes": auto_fixes, "errors": errors,
    }


def import_db_file(conn: kuzu.Connection, file_bytes: bytes, tree_id: str = "") -> dict:
    """Import from a SQLite .db file (from legacy or v2 projects)."""
    errors = []
    auto_fixes = []

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.write(file_bytes)
    tmp.close()

    try:
        src = sqlite3.connect(tmp.name)
        src.row_factory = sqlite3.Row
        cursor = src.cursor()
        tables = [r[0] for r in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        if "people" in tables:
            return _import_legacy_db(conn, src, errors, auto_fixes, tree_id)
        elif "person" in tables:
            return _import_starter_db(conn, src, errors, auto_fixes, tree_id)
        else:
            return {
                "people": 0, "relationships": 0, "auto_fixes": [],
                "errors": [{"line": 0, "type": "unknown_schema",
                            "message": f"Unrecognized DB schema. Tables: {', '.join(tables)}"}]
            }
    finally:
        src.close()
        os.unlink(tmp.name)


def _import_legacy_db(conn, src, errors, auto_fixes, tree_id=""):
    """Import from legacy SQLite DB with 'people' and 'relationships' tables."""
    crud.clear_all(conn, tree_id=tree_id)
    cursor = src.cursor()
    people_rows = cursor.execute("SELECT id, raw_name, gender, details FROM people").fetchall()
    id_map = {}

    name_counts = defaultdict(list)
    for row in people_rows:
        name_counts[clean_name(row["raw_name"])].append(row)

    for row in people_rows:
        name = clean_name(row["raw_name"])
        sex = row["gender"] if row["gender"] in ("M", "F") else "U"
        details = row["details"] if row["details"] else None

        if len(name_counts[name]) > 1:
            name = f"{name} (#{row['id']})"
            auto_fixes.append({
                "line": 0, "type": "auto_renamed",
                "message": f'Duplicate name disambiguated to "{name}"',
                "original": clean_name(row["raw_name"]), "resolved": name,
            })

        p = crud.create_person(conn, name, sex, details, tree_id=tree_id)
        id_map[row["id"]] = p

    rel_count = 0
    rel_rows = cursor.execute(
        "SELECT person1_id, relation, person2_id FROM relationships"
    ).fetchall()
    for row in rel_rows:
        p1 = id_map.get(row["person1_id"])
        p2 = id_map.get(row["person2_id"]) if row["person2_id"] else None

        if row["relation"] == "Child" and p1 and p2:
            crud.create_relationship(conn, p2["id"], p1["id"], "PARENT_OF")
            rel_count += 1
        elif row["relation"] == "Spouse" and p1 and p2:
            crud.create_relationship(conn, p1["id"], p2["id"], "SPOUSE_OF")
            rel_count += 1
        elif row["relation"] == "Earliest Ancestor":
            pass
        elif p1 is None or (p2 is None and row["relation"] != "Earliest Ancestor"):
            errors.append({
                "line": 0, "type": "missing_person",
                "message": f'Relationship references missing person ID(s)',
            })

    return {
        "people": len(crud.list_people(conn, tree_id=tree_id)), "relationships": rel_count,
        "auto_fixes": auto_fixes, "errors": errors,
    }


def _import_starter_db(conn, src, errors, auto_fixes, tree_id=""):
    """Import from starter schema SQLite DB with 'person' and 'relationship' tables."""
    crud.clear_all(conn, tree_id=tree_id)
    cursor = src.cursor()
    people_rows = cursor.execute("SELECT id, display_name, sex, notes FROM person").fetchall()
    id_map = {}

    for row in people_rows:
        sex = row["sex"] if row["sex"] in ("M", "F", "U") else "U"
        p = crud.create_person(conn, row["display_name"], sex, row["notes"], tree_id=tree_id)
        id_map[row["id"]] = p

    rel_count = 0
    rel_rows = cursor.execute(
        "SELECT from_person_id, to_person_id, type FROM relationship"
    ).fetchall()
    for row in rel_rows:
        p_from = id_map.get(row["from_person_id"])
        p_to = id_map.get(row["to_person_id"])
        if p_from and p_to:
            rel_type = row["type"]
            if rel_type in ("PARENT_OF", "SPOUSE_OF", "SIBLING_OF"):
                crud.create_relationship(conn, p_from["id"], p_to["id"], rel_type)
                rel_count += 1
        else:
            errors.append({
                "line": 0, "type": "missing_person",
                "message": "Relationship references missing person ID(s)",
            })

    return {
        "people": len(crud.list_people(conn, tree_id=tree_id)), "relationships": rel_count,
        "auto_fixes": auto_fixes, "errors": errors,
    }
