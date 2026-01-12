from fastapi import FastAPI, Depends, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .db import get_db, engine
from .models import Base, Tree, TreeVersion
from . import crud, schemas, graph
#from .plotly_graph.db_plotly import build_plotly_figure_from_db
#from .plotly_graph.plotly_render import build_plotly_figure_from_db

app = FastAPI()
Base.metadata.create_all(bind=engine)

@app.get("/", include_in_schema=False)
def ui():
    return FileResponse("web/index.html")

@app.get("/web/app.js", include_in_schema=False)
def ui_js():
    return FileResponse("web/app.js")

@app.get("/people", response_model=list[schemas.PersonOut])
def people(
    tree_id: int | None = Query(None, description="Optional tree id to filter by"),
    body: schemas.TreeFilter | None = Body(None),
    db: Session = Depends(get_db),
):
    # prefer explicit body.tree_id/tree_version_id if provided
    effective_tree_id = body.tree_id if body and body.tree_id is not None else tree_id
    effective_tree_version = body.tree_version_id if body and body.tree_version_id is not None else None
    return crud.list_people(db, tree_id=effective_tree_id, tree_version_id=effective_tree_version)

@app.post("/people", response_model=schemas.PersonOut)
def add_person(body: schemas.PersonCreate, db: Session = Depends(get_db)):
    return crud.create_person(db, body.display_name, body.sex, body.notes, tree_id=body.tree_id, tree_version_id=body.tree_version_id)

@app.post("/relationships")
def add_rel(body: schemas.RelCreate, db: Session = Depends(get_db)):
    return crud.create_relationship(db, body.from_person_id, body.to_person_id, body.type, tree_id=body.tree_id, tree_version_id=body.tree_version_id)


@app.post("/trees/import", response_model=schemas.TreeImportOut)
def import_tree(body: schemas.TreeImportRequest, db: Session = Depends(get_db)):
    # body may contain name, source_filename, and optional tree_id
    name = body.name
    source = body.source_filename
    tree_id = body.tree_id
    tree, tv = crud.create_or_increment_tree_version(db, name=name, source_filename=source, tree_id=tree_id)
    return {"tree_id": tree.id, "tree_version_id": tv.id, "version": tv.version}


@app.get("/trees", response_model=list[schemas.TreeListItem])
def list_trees(db: Session = Depends(get_db)):
    trees = db.query(Tree).all()
    out = []
    for t in trees:
        active = db.query(TreeVersion).filter(TreeVersion.tree_id == t.id, TreeVersion.active == True).order_by(TreeVersion.version.desc()).first()
        out.append({"id": t.id, "name": t.name, "description": t.description, "created_at": t.created_at.isoformat() if t.created_at else None, "active_version_id": active.id if active else None})
    return out


@app.get("/trees/{tree_id}/versions", response_model=list[schemas.TreeVersionItem])
def list_tree_versions(tree_id: int, db: Session = Depends(get_db)):
    versions = db.query(TreeVersion).filter(TreeVersion.tree_id == tree_id).order_by(TreeVersion.version.asc()).all()
    out = []
    for v in versions:
        out.append({"id": v.id, "tree_id": v.tree_id, "version": v.version, "source_filename": v.source_filename, "created_at": v.created_at.isoformat() if v.created_at else None, "active": bool(v.active)})
    return out


@app.patch("/trees/{tree_id}")
def update_tree(tree_id: int, body: schemas.TreeUpdate, db: Session = Depends(get_db)):
    try:
        t = crud.update_tree(db, tree_id=tree_id, name=body.name, description=body.description)
    except Exception as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
    return {"id": t.id, "name": t.name, "description": t.description, "created_at": t.created_at.isoformat() if t.created_at else None}


@app.post("/trees/{tree_id}/versions/{base_version_id}/drafts", response_model=schemas.DraftOut)
def create_draft(tree_id: int, base_version_id: int, body: schemas.DraftCreate, db: Session = Depends(get_db)):
    d = crud.create_draft(db, tree_id=tree_id, base_tree_version_id=base_version_id, change_type=body.change_type, payload=body.payload)
    return {"id": d.id, "tree_id": d.tree_id, "base_tree_version_id": d.base_tree_version_id, "change_type": d.change_type, "payload": d.payload, "created_at": d.created_at.isoformat()}


@app.get("/trees/{tree_id}/versions/{base_version_id}/drafts", response_model=list[schemas.DraftOut])
def list_drafts(tree_id: int, base_version_id: int, db: Session = Depends(get_db)):
    drafts = crud.list_drafts(db, tree_id=tree_id, base_tree_version_id=base_version_id)
    out = []
    for d in drafts:
        out.append({"id": d.id, "tree_id": d.tree_id, "base_tree_version_id": d.base_tree_version_id, "change_type": d.change_type, "payload": d.payload, "created_at": d.created_at.isoformat()})
    return out


@app.post("/trees/{tree_id}/versions/{base_version_id}/publish", response_model=schemas.TreeImportOut)
def publish_drafts(tree_id: int, base_version_id: int, db: Session = Depends(get_db)):
    tree, tv = crud.publish_drafts(db, tree_id=tree_id, base_tree_version_id=base_version_id)
    return {"tree_id": tree.id, "tree_version_id": tv.id, "version": tv.version}


@app.delete("/trees/{tree_id}/versions/{base_version_id}/drafts/{draft_id}")
def delete_draft(tree_id: int, base_version_id: int, draft_id: int, db: Session = Depends(get_db)):
    crud.delete_draft(db, draft_id)
    return {"ok": True}


@app.delete("/trees/{tree_id}/versions/{base_version_id}/drafts")
def delete_all_drafts(tree_id: int, base_version_id: int, db: Session = Depends(get_db)):
    count = crud.delete_drafts_for_base(db, tree_id=tree_id, base_tree_version_id=base_version_id)
    return {"deleted": count}

# ✅ NEW: Plotly figure JSON
@app.get("/api/plotly")
def get_plotly(
    tree_id: int | None = Query(None),
    tree_version_id: int | None = Query(None),
    body: schemas.TreeFilter | None = Body(None),
    db: Session = Depends(get_db),
):
    # prefer explicit body values first, then query params
    effective_tree_id = body.tree_id if body and body.tree_id is not None else tree_id
    effective_tree_version = body.tree_version_id if body and body.tree_version_id is not None else tree_version_id
    return graph.build_plotly_figure_json(db, tree_id=effective_tree_id, tree_version_id=effective_tree_version)

@app.get("/health")
def health():
    return {"ok": True}

