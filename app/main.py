import re
import os
import hashlib
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse, Response, HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from .db import get_database, get_conn
from . import crud, schemas, graph, sharing
from .importer import import_csv_text, import_db_file

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Admin authentication via environment variable
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_cookie_secret = os.environ.get("COOKIE_SECRET", secrets.token_hex(16))


def _make_admin_token():
    return hashlib.sha256(f"{ADMIN_PASSWORD}:{_cookie_secret}".encode()).hexdigest()


# Paths that don't require admin auth
_PUBLIC_PATHS = {"/login", "/health"}
_PUBLIC_PREFIXES = ("/view/",)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not ADMIN_PASSWORD:
            return await call_next(request)
        path = request.url.path
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)
        token = request.cookies.get("admin_token")
        if token != _make_admin_token():
            return RedirectResponse("/login", status_code=302)
        return await call_next(request)


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
app.add_middleware(AdminAuthMiddleware)


@app.get("/login", include_in_schema=False)
def login_page():
    if not ADMIN_PASSWORD:
        return RedirectResponse("/", status_code=302)
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Login — Family Tree</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;height:100vh}
.card{background:white;padding:40px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.1);width:340px;text-align:center}
.card h1{font-size:48px;margin-bottom:8px}
.card h2{font-size:20px;color:#2c3e50;margin-bottom:24px}
input{width:100%;padding:10px 14px;border:1px solid #ccc;border-radius:4px;font-size:15px;margin-bottom:14px}
button{width:100%;padding:10px;background:#3498db;color:white;border:none;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#2980b9}
.error{color:#e74c3c;font-size:13px;margin-bottom:10px;display:none}
</style></head><body>
<div class="card">
<h1>&#x1F333;</h1><h2>Family Tree</h2>
<div class="error" id="err">Incorrect password</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Enter admin password" autofocus>
<button type="submit">Log In</button>
</form></div></body></html>""")


@app.post("/login", include_in_schema=False)
async def login_submit(request: Request):
    form = await request.form()
    password = form.get("password", "")
    if password != ADMIN_PASSWORD:
        return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Login — Family Tree</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;height:100vh}
.card{background:white;padding:40px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.1);width:340px;text-align:center}
.card h1{font-size:48px;margin-bottom:8px}
.card h2{font-size:20px;color:#2c3e50;margin-bottom:24px}
input{width:100%;padding:10px 14px;border:1px solid #ccc;border-radius:4px;font-size:15px;margin-bottom:14px}
button{width:100%;padding:10px;background:#3498db;color:white;border:none;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#2980b9}
.error{color:#e74c3c;font-size:13px;margin-bottom:10px}
</style></head><body>
<div class="card">
<h1>&#x1F333;</h1><h2>Family Tree</h2>
<div class="error">Incorrect password</div>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Enter admin password" autofocus>
<button type="submit">Log In</button>
</form></div></body></html>""", status_code=401)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("admin_token", _make_admin_token(), httponly=True, samesite="lax")
    return response


@app.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("admin_token")
    return response


@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
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
    # Validate constraints
    if body.type == "PARENT_OF":
        child_parents = crud.count_parents(conn, body.to_person_id)
        if child_parents >= 1:
            raise HTTPException(400, "This person already has a parent. Use 'Replace Parent' to change it.")
    if body.type == "SPOUSE_OF":
        from_spouses = crud.count_spouses(conn, body.from_person_id)
        to_spouses = crud.count_spouses(conn, body.to_person_id)
        if from_spouses >= 1:
            raise HTTPException(400, "This person already has a spouse.")
        if to_spouses >= 1:
            raise HTTPException(400, "The other person already has a spouse.")

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


@app.get("/people/{person_id}/parents", response_model=list[schemas.PersonOut])
def get_parents(person_id: str, conn=Depends(get_conn)):
    """Get the parents of a person."""
    return crud.get_parents(conn, person_id)


class SetParentRequest(BaseModel):
    """Set parent: either create a new person or link an existing one."""
    existing_person_id: str | None = None  # Link existing person
    display_name: str | None = None         # Create new person
    sex: str = "U"
    notes: str | None = None


@app.post("/people/{person_id}/set-parent")
def set_parent(person_id: str, body: SetParentRequest, conn=Depends(get_conn)):
    """Set (or replace) the parent of a person.
    Provide existing_person_id to link an existing person,
    or display_name to create a new one."""
    existing_parents = crud.get_parents(conn, person_id)
    removed = []
    # Remove existing parent relationships if any
    for parent in existing_parents:
        crud.delete_parent_relationship(conn, parent["id"], person_id)
        removed.append(parent["display_name"])

    # Determine the parent: existing or new
    if body.existing_person_id:
        parent_person = crud.get_person(conn, body.existing_person_id)
        if not parent_person:
            raise HTTPException(404, "Selected parent person not found")
        # Prevent self-parenting
        if body.existing_person_id == person_id:
            raise HTTPException(400, "A person cannot be their own parent")
    elif body.display_name:
        parent_person = crud.create_person(conn, body.display_name, body.sex, body.notes)
    else:
        raise HTTPException(400, "Provide existing_person_id or display_name")

    crud.create_relationship(conn, parent_person["id"], person_id, "PARENT_OF")
    return {
        "parent": parent_person,
        "removed_parents": removed,
    }


@app.get("/people/{person_id}/relationship-counts")
def relationship_counts(person_id: str, conn=Depends(get_conn)):
    """Get counts of parents and spouses for validation."""
    return {
        "parents": crud.count_parents(conn, person_id),
        "spouses": crud.count_spouses(conn, person_id),
    }


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


# ── Sharing endpoints ──


class ShareCreateRequest(BaseModel):
    dataset: str


class ViewerAddRequest(BaseModel):
    email: str
    name: str = ""


class ViewerAuthRequest(BaseModel):
    email: str


@app.post("/api/shares")
def create_share(body: ShareCreateRequest, conn=Depends(get_conn)):
    """Create a share link for a dataset."""
    link = sharing.create_share_link(conn, body.dataset)
    return link


@app.get("/api/shares")
def list_shares(conn=Depends(get_conn)):
    """List all share links."""
    links = sharing.list_share_links(conn)
    for link in links:
        link["viewers"] = sharing.list_viewers(conn, link["token"])
    return links


@app.delete("/api/shares/{token}")
def delete_share(token: str, conn=Depends(get_conn)):
    """Delete a share link."""
    sharing.delete_share_link(conn, token)
    return {"ok": True}


@app.post("/api/shares/{token}/viewers")
def add_share_viewer(token: str, body: ViewerAddRequest, conn=Depends(get_conn)):
    """Add a viewer to a share link."""
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer = sharing.add_viewer(conn, token, body.email, body.name)
    return viewer


@app.delete("/api/shares/{token}/viewers/{viewer_id}")
def remove_share_viewer(token: str, viewer_id: str, conn=Depends(get_conn)):
    """Remove a viewer from a share link."""
    sharing.remove_viewer(conn, token, viewer_id)
    return {"ok": True}


@app.get("/api/shares/{token}/viewers")
def get_share_viewers(token: str, conn=Depends(get_conn)):
    """List viewers for a share link."""
    return sharing.list_viewers(conn, token)


@app.get("/api/shares/{token}/access-log")
def get_share_access_log(token: str, conn=Depends(get_conn)):
    """Get access log for a share link."""
    return sharing.get_access_log(conn, token)


@app.post("/view/{token}/auth")
def viewer_auth(token: str, body: ViewerAuthRequest, request: Request, conn=Depends(get_conn)):
    """Authenticate a viewer by email for a shared link."""
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer = sharing.check_viewer_access(conn, token, body.email)
    if not viewer:
        raise HTTPException(403, "You don't have access to this tree. Contact the owner to request access.")
    ip = request.client.host if request.client else ""
    sharing.log_access(conn, token, viewer["id"], ip)
    return {"ok": True, "viewer": viewer, "dataset": link["dataset"]}


@app.get("/view/{token}/graph")
def viewer_graph(token: str, email: str, conn=Depends(get_conn)):
    """Get graph data for a shared link (requires authorized email)."""
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer = sharing.check_viewer_access(conn, token, email)
    if not viewer:
        raise HTTPException(403, "Access denied")
    return graph.build_graph(conn, dataset=link["dataset"])


@app.get("/view/{token}", response_class=HTMLResponse)
def viewer_page(token: str, conn=Depends(get_conn)):
    """Serve the read-only viewer page."""
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer_html = Path(__file__).resolve().parent.parent / "web" / "viewer.html"
    if not viewer_html.exists():
        raise HTTPException(500, "Viewer page not found")
    return HTMLResponse(viewer_html.read_text(encoding="utf-8"))


@app.get("/api/export/csv")
def export_csv(conn=Depends(get_conn)):
    """Export current data as legacy CSV format."""
    import csv as csv_mod, io as io_mod

    people_list = crud.list_people(conn)
    id_to_person = {p["id"]: p for p in people_list}

    # Collect all edges
    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF"]:
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

    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=family_tree.csv"}
    )
