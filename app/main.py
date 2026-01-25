import json
import tempfile
import glob
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, Query, Body, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .db import get_db, engine
from .models import Base, Tree, TreeVersion
from . import crud, schemas, graph
from .importers.family_tree_text import parse_family_tree_txt, build_people_set, build_relationship_requests, detect_duplicates
from .importers.family_tree_json import parse_family_tree_json, extract_people_for_import, extract_relationships_for_import
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


@app.post("/import")
async def import_file(
    file: UploadFile = File(...),
    tree_name: str | None = Query(None),
    tree_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Import a family tree file (txt, csv, or json).
    If tree_id is provided, creates a new version of that tree.
    Otherwise, creates a new tree with a unique name.
    """
    if not file.filename:
        raise ValueError("File is required")
    
    # Determine file type
    file_ext = Path(file.filename).suffix.lower()
    is_json = file_ext == ".json"
    is_text = file_ext in (".txt", ".csv")
    
    if not is_json and not is_text:
        raise ValueError(f"Unsupported file format: {file_ext}. Use .txt, .csv, or .json")
    
    try:
        # Read file content
        content = await file.read()
        
        # Save to temp file for parsing
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # Parse based on format
        people_payloads = {}
        rel_reqs = []
        rows = None
        json_data = None
        warnings = []
        errors = []
        
        if is_json:
            json_data = parse_family_tree_json(tmp_path)
            people_payloads = extract_people_for_import(json_data)
        else:  # txt or csv
            rows = parse_family_tree_txt(tmp_path)
            
            # Detect duplicates before processing
            duplicate_warnings = detect_duplicates(rows, file.filename)
            if duplicate_warnings:
                warnings.extend(duplicate_warnings)
            
            people_payloads = build_people_set(rows)
        
        # If tree_id is provided, add as new version to existing tree
        if tree_id is not None:
            tree, tv = crud.create_or_increment_tree_version(
                db,
                name=None,  # Keep existing tree name
                source_filename=file.filename,
                tree_id=tree_id
            )
        else:
            # Determine tree name (use provided name or filename)
            base_name = tree_name if tree_name else Path(file.filename).stem
            
            # Ensure unique tree name by checking for duplicates
            existing_tree = db.query(Tree).filter(Tree.name == base_name).first()
            if existing_tree:
                # Find next available name with suffix
                counter = 2
                while db.query(Tree).filter(Tree.name == f"{base_name}_{counter}").first():
                    counter += 1
                base_name = f"{base_name}_{counter}"
            
            # Always create a brand new tree (not a version)
            tree = Tree(name=base_name, description=f"Imported from {file.filename}")
            db.add(tree)
            db.commit()
            db.refresh(tree)
            
            # Create initial version
            tv = TreeVersion(tree_id=tree.id, version=1, source_filename=file.filename, active=True)
            db.add(tv)
            db.commit()
            db.refresh(tv)
        
        # Import people
        name_to_id: dict[str, str] = {}
        for name, payload in people_payloads.items():
            p = crud.create_person(
                db,
                display_name=payload.get('display_name', ''),
                sex=payload.get('sex', 'U'),
                notes=payload.get('notes'),
                tree_id=tree.id,
                tree_version_id=tv.id
            )
            name_to_id[name] = str(p.id)
        
        # Build relationships based on format
        if is_json and json_data:
            # For JSON, map IDs using display_name lookup
            for rel in json_data.get('relationships', []):
                from_id = rel.get('from_person_id')
                to_id = rel.get('to_person_id')
                rel_type = rel.get('type', 'CHILD_OF')
                
                # Only process CHILD_OF
                if rel_type != 'CHILD_OF':
                    warnings.append(f"Skipped relationship: Type '{rel_type}' not yet supported")
                    continue
                
                # Find person by ID in json people array
                from_person = next((p for p in json_data.get('people', []) if p.get('id') == from_id), None)
                if from_person:
                    resolved_from = name_to_id.get(from_person.get('display_name'))
                    if resolved_from:
                        resolved_to = None
                        if to_id:
                            to_person = next((p for p in json_data.get('people', []) if p.get('id') == to_id), None)
                            if to_person:
                                resolved_to = name_to_id.get(to_person.get('display_name'))
                        
                        rel_reqs.append((1, {
                            'from_person_id': resolved_from,
                            'to_person_id': resolved_to,
                            'type': rel_type,
                        }))
        else:
            # For txt/csv
            rel_reqs, txt_warnings = build_relationship_requests(rows, name_to_id)
            warnings.extend(txt_warnings)
        
        # Import relationships
        for line_no, rel_payload in rel_reqs:
            try:
                crud.create_relationship(
                    db,
                    from_id=rel_payload.get('from_person_id'),
                    to_id=rel_payload.get('to_person_id'),
                    rel_type=rel_payload.get('type'),
                    tree_id=tree.id,
                    tree_version_id=tv.id
                )
            except Exception as e:
                errors.append(f"Line {line_no}: Failed to create relationship - {str(e)}")
        
        # Cleanup
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass
        
        return {
            "tree_id": tree.id,
            "tree_version_id": tv.id,
            "version": tv.version,
            "people_count": len(name_to_id),
            "relationships_count": len(rel_reqs),
            "warnings": warnings,
            "errors": errors,
        }
    
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Import failed: {str(e)}",
                "details": str(e)
            }
        )


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


@app.get("/export", include_in_schema=True)
def export_data(
    tree_id: int | None = Query(None, description="Optional tree id to export"),
    tree_version_id: int | None = Query(None, description="Optional tree version id to export"),
    save_to_disk: bool = Query(False, description="Save to data/exports/ instead of downloading"),
    prefer_non_empty: bool = Query(True, description="If active version is empty, fallback to latest non-empty version"),
    filename: str | None = Query(None, description="Custom filename (without .json extension)"),
    db: Session = Depends(get_db),
):
    """Export people and relationships as a JSON file.
    
    By default, returns file for download. Set save_to_disk=true to save to data/exports/ folder.
    Keeps last 5 versions per tree when saving to disk.
    """
    payload = crud.export_data(db, tree_id=tree_id, tree_version_id=tree_version_id)

    # If exporting by tree_id and no explicit tree_version_id, optionally
    # fallback to the latest non-empty version when the active is empty.
    if (
        prefer_non_empty
        and tree_id is not None
        and tree_version_id is None
        and payload
        and len(payload.get("people", [])) == 0
        and len(payload.get("relationships", [])) == 0
    ):
        versions = (
            db.query(TreeVersion)
            .filter(TreeVersion.tree_id == tree_id)
            .order_by(TreeVersion.version.desc())
            .all()
        )
        for v in versions:
            candidate = crud.export_data(db, tree_id=tree_id, tree_version_id=v.id)
            if len(candidate.get("people", [])) > 0 or len(candidate.get("relationships", [])) > 0:
                payload = candidate
                break

    if save_to_disk:
        # Save to data/exports/ directory
        exports_dir = Path("data/exports")
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename if not provided
        if filename:
            file_path = exports_dir / f"{filename}.json"
            prefix_for_cleanup = None  # Don't cleanup custom filenames
        else:
            # Use tree name and version from export payload
            tree_info = payload.get("tree")
            version_info = payload.get("tree_version")
            
            if tree_info and version_info:
                # Sanitize tree name for filename (replace spaces and special chars)
                safe_name = tree_info["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")
                
                # Check if a file already exists for this tree version
                existing_pattern = str(exports_dir / f"{safe_name}_v{version_info['version']}_*.json")
                existing_files = glob.glob(existing_pattern)
                
                if existing_files:
                    # Overwrite the existing file for this version (use the first one)
                    file_path = Path(existing_files[0])
                else:
                    # New version, create with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = exports_dir / f"{safe_name}_v{version_info['version']}_{timestamp}.json"
                
                prefix_for_cleanup = safe_name  # Use tree name prefix for cleanup
            elif tree_info:
                safe_name = tree_info["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")
                
                # Check if a file already exists for this tree (without version)
                existing_pattern = str(exports_dir / f"{safe_name}_*.json")
                existing_files = [f for f in glob.glob(existing_pattern) if "_v" not in f]
                
                if existing_files:
                    file_path = Path(existing_files[0])
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = exports_dir / f"{safe_name}_{timestamp}.json"
                
                prefix_for_cleanup = safe_name
            else:
                # No tree info - check if generic export exists
                existing_pattern = str(exports_dir / "family_tree_export_*.json")
                existing_files = glob.glob(existing_pattern)
                
                if existing_files:
                    file_path = Path(existing_files[0])
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = exports_dir / f"family_tree_export_{timestamp}.json"
                
                prefix_for_cleanup = "family_tree_export"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        
        # Cleanup old versions: keep only the 5 most recent exports for this tree
        if prefix_for_cleanup:
            cleanup_old_exports(exports_dir, prefix_for_cleanup)
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Export saved to {str(file_path)}",
            "path": str(file_path)
        })
    else:
        # Return file for download
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        with open(tmp.name, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        
        # Generate download filename with tree name if available
        tree_info = payload.get("tree")
        version_info = payload.get("tree_version")
        download_filename = "family_tree_export.json"
        if tree_info and version_info:
            safe_name = tree_info["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")
            download_filename = f"{safe_name}_v{version_info['version']}.json"
        elif tree_info:
            safe_name = tree_info["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")
            download_filename = f"{safe_name}.json"
        
        return FileResponse(tmp.name, media_type="application/json", filename=download_filename)


def cleanup_old_exports(exports_dir: Path, prefix: str, keep_count: int = 5):
    """Keep only the most recent `keep_count` exports matching the prefix pattern."""
    # Find all export files matching the prefix (e.g., "gezaweldeamlak_v*.json")
    pattern = str(exports_dir / f"{prefix}_v*.json")
    matching_files = sorted(glob.glob(pattern), key=lambda p: Path(p).stat().st_mtime, reverse=True)
    
    # Delete files beyond the keep_count most recent
    for old_file in matching_files[keep_count:]:
        try:
            Path(old_file).unlink()
        except Exception:
            pass  # Ignore errors if file can't be deleted

