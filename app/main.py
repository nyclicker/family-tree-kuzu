import re
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from .db import get_database, get_conn
from . import crud, schemas, graph
from .importer import import_csv_text, import_db_file

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _clean_display_names(conn):
    """Post-import: strip \\n suffixes and parenthetical disambiguations from display names."""
    result = conn.execute("MATCH (p:Person) RETURN p.id, p.display_name")
    updates = []
    while result.has_next():
        row = result.get_next()
        pid, name = row[0], row[1]
        clean = name
        # Remove newline and everything after it
        nl = clean.find('\n')
        if nl != -1:
            clean = clean[:nl]
        # Remove trailing parenthetical e.g. " (Desta)"
        clean = re.sub(r'\s*\([^)]*\)\s*$', '', clean)
        clean = clean.strip()
        if clean and clean != name:
            updates.append((pid, clean))
    for pid, clean in updates:
        conn.execute(
            "MATCH (p:Person) WHERE p.id = $id SET p.display_name = $name",
            {"id": pid, "name": clean}
        )


class DatasetLoadRequest(BaseModel):
    files: list[str]
    combine: bool = False


@asynccontextmanager
async def lifespan(app):
    get_database()  # Initialize KuzuDB schema
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse("web/index.html")


@app.get("/web/app.js", include_in_schema=False)
def ui_js():
    return FileResponse("web/app.js")


@app.get("/people", response_model=list[schemas.PersonOut])
def people(conn=Depends(get_conn)):
    return crud.list_people(conn)


@app.post("/people", response_model=schemas.PersonOut)
def add_person(body: schemas.PersonCreate, conn=Depends(get_conn)):
    return crud.create_person(conn, body.display_name, body.sex, body.notes)


@app.post("/relationships")
def add_rel(body: schemas.RelCreate, conn=Depends(get_conn)):
    result = crud.create_relationship(conn, body.from_person_id, body.to_person_id, body.type)
    if body.type == "SPOUSE_OF":
        merged = crud.merge_spouse_children(conn, body.from_person_id, body.to_person_id)
        if merged:
            result["merged_children"] = merged
    return result


@app.put("/people/{person_id}", response_model=schemas.PersonOut)
def update_person(person_id: str, body: schemas.PersonUpdate, conn=Depends(get_conn)):
    p = crud.update_person(conn, person_id, body.display_name, body.sex, body.notes)
    if not p:
        from fastapi import HTTPException
        raise HTTPException(404, "Person not found")
    return p


@app.delete("/people/{person_id}")
def delete_person(person_id: str, conn=Depends(get_conn)):
    crud.delete_person(conn, person_id)
    return {"ok": True}


@app.delete("/relationships/{rel_id}")
def delete_rel(rel_id: str, conn=Depends(get_conn)):
    crud.delete_relationship(conn, rel_id)
    return {"ok": True}


@app.get("/graph", response_model=schemas.GraphOut)
def get_graph(conn=Depends(get_conn)):
    return graph.build_graph(conn)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/datasets")
def list_datasets():
    """List available data files in the data directory."""
    if not DATA_DIR.exists():
        return []
    files = sorted(list(DATA_DIR.glob("*.csv")) + list(DATA_DIR.glob("*.txt")))
    return [{"name": f.stem, "filename": f.name} for f in files]


@app.post("/api/import/dataset")
def import_dataset(body: DatasetLoadRequest, conn=Depends(get_conn)):
    """Load specific data files. combine=false clears DB first; combine=true adds to existing."""
    if not DATA_DIR.exists():
        return {"error": "No data directory"}

    all_people = 0
    all_rels = 0
    all_fixes = []
    all_errors = []
    dataset_names = []

    for i, filename in enumerate(body.files):
        filepath = DATA_DIR / filename
        if not filepath.exists():
            all_errors.append({"line": 0, "type": "file_not_found",
                               "message": f"File not found: {filename}"})
            continue
        clear = (i == 0 and not body.combine)
        result = import_csv_text(
            conn, filepath.read_text(encoding="utf-8"),
            dataset=filepath.stem, clear_first=clear
        )
        all_people = result["people"]
        all_rels += result["relationships"]
        all_fixes.extend(result["auto_fixes"])
        all_errors.extend(result["errors"])
        dataset_names.append(filepath.stem)

    # Clean display names: strip \n suffixes and (parent) disambiguations
    _clean_display_names(conn)
    all_people = len(crud.list_people(conn))

    name = ", ".join(dataset_names) if len(dataset_names) > 1 else (dataset_names[0] if dataset_names else "")
    return {
        "people": all_people, "relationships": all_rels,
        "auto_fixes": all_fixes, "errors": all_errors,
        "dataset_name": name,
    }


@app.post("/api/clear")
def clear_data(conn=Depends(get_conn)):
    """Clear all data from the graph database."""
    crud.clear_all(conn)
    return {"ok": True}


@app.post("/api/import/upload")
async def import_upload(file: UploadFile = File(...), conn=Depends(get_conn)):
    contents = await file.read()
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext == ".db":
        result = import_db_file(conn, contents)
    elif ext in (".csv", ".txt", ""):
        text = contents.decode("utf-8", errors="replace")
        result = import_csv_text(conn, text)
    else:
        return {"error": f"Unsupported file type: {ext}. Use .csv, .txt, or .db"}
    _clean_display_names(conn)
    result["people"] = len(crud.list_people(conn))
    result["dataset_name"] = Path(name).stem
    return result


@app.get("/api/export/csv")
def export_csv(conn=Depends(get_conn)):
    """Export current data as legacy CSV format."""
    import csv as csv_mod, io as io_mod

    people_list = crud.list_people(conn)
    id_to_person = {p["id"]: p for p in people_list}

    # Collect all edges
    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF", "SIBLING_OF"]:
        result = conn.execute(
            f"MATCH (a:Person)-[r:{rel_type}]->(b:Person) RETURN a.id, b.id"
        )
        while result.has_next():
            row = result.get_next()
            edges.append({"from_id": row[0], "to_id": row[1], "type": rel_type})

    # Build CSV
    children_ids = {e["to_id"] for e in edges if e["type"] == "PARENT_OF"}
    buf = io_mod.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(["Person 1", "Relation", "Person 2", "Gender", "Details"])

    for p in people_list:
        if p["id"] not in children_ids:
            dn = p["display_name"].replace("\n", "\\n")
            writer.writerow([dn, "Earliest Ancestor", "", p["sex"], p["notes"] or ""])

    for e in edges:
        p1 = id_to_person.get(e["from_id"])
        p2 = id_to_person.get(e["to_id"])
        if not p1 or not p2:
            continue
        dn1 = p1["display_name"].replace("\n", "\\n")
        dn2 = p2["display_name"].replace("\n", "\\n")
        if e["type"] == "PARENT_OF":
            writer.writerow([dn2, "Child", dn1, p2["sex"], p2["notes"] or ""])
        elif e["type"] == "SPOUSE_OF":
            writer.writerow([dn1, "Spouse", dn2, "", ""])
        elif e["type"] == "SIBLING_OF":
            writer.writerow([dn1, "Sibling", dn2, "", ""])

    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=family_tree.csv"}
    )
