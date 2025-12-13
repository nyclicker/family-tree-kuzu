from sqlalchemy.orm import Session
from .models import Person, Relationship

def build_graph(db: Session):
    people = db.query(Person).all()
    rels = db.query(Relationship).all()
    nodes = [{"data": {"id": p.id, "label": p.display_name}} for p in people]
    edges = [{
        "data": {"id": r.id, "source": r.from_person_id, "target": r.to_person_id, "type": r.type.value}
    } for r in rels]
    return {"nodes": nodes, "edges": edges}
