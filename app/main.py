from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .db import get_db
from . import crud, schemas, graph

app = FastAPI()

@app.get("/", include_in_schema=False)
def ui():
    return FileResponse("web/index.html")

@app.get("/web/app.js", include_in_schema=False)
def ui_js():
    return FileResponse("web/app.js")

@app.get("/people", response_model=list[schemas.PersonOut])
def people(db: Session = Depends(get_db)):
    return crud.list_people(db)

@app.post("/people", response_model=schemas.PersonOut)
def add_person(body: schemas.PersonCreate, db: Session = Depends(get_db)):
    return crud.create_person(db, body.display_name, body.sex, body.notes)

@app.post("/relationships")
def add_rel(body: schemas.RelCreate, db: Session = Depends(get_db)):
    return crud.create_relationship(db, body.from_person_id, body.to_person_id, body.type)

@app.get("/graph", response_model=schemas.GraphOut)
def get_graph(db: Session = Depends(get_db)):
    return graph.build_graph(db)

@app.get("/health")
def health():
    return {"ok": True}
