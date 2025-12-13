from sqlalchemy.orm import Session
from .models import Person, Relationship, Sex, RelType

def create_person(db: Session, display_name: str, sex: str, notes: str | None):
    p = Person(display_name=display_name, sex=Sex(sex), notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return p

def list_people(db: Session):
    return db.query(Person).order_by(Person.display_name.asc()).all()

def create_relationship(db: Session, from_id: str, to_id: str, rel_type: str):
    r = Relationship(from_person_id=from_id, to_person_id=to_id, type=RelType(rel_type))
    db.add(r); db.commit(); db.refresh(r)
    return r
