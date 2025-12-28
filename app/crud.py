from sqlalchemy.orm import Session
from .models import Person, Relationship, Sex, RelType

def create_person(db: Session, display_name: str, sex: str, notes: str | None):
    p = Person(display_name=display_name, sex=Sex(sex), notes=notes)
    db.add(p); db.commit(); db.refresh(p)
    return p

def list_people(db: Session):
    return db.query(Person).order_by(Person.display_name.asc()).all()

def create_relationship(db: Session, from_id: str, to_id: str | None, rel_type: str):
    rt = RelType(rel_type)

    if rt == RelType.EARLIEST_ANCESTOR:
        # optional but helpful: enforce only one root
        existing = db.query(Relationship).filter(Relationship.type == RelType.EARLIEST_ANCESTOR).first()
        if existing and existing.from_person_id != from_id:
            raise ValueError("An EARLIEST_ANCESTOR already exists. Remove it before setting a new one.")
        to_id = None

    if rt == RelType.CHILD_OF and not to_id:
        raise ValueError("to_person_id is required for CHILD_OF")

    r = Relationship(from_person_id=from_id, to_person_id=to_id, type=rt)
    db.add(r); db.commit(); db.refresh(r)
    return r

