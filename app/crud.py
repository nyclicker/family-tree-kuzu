from sqlalchemy.orm import Session
from .models import Person, Relationship, Sex, RelType, Tree, TreeVersion
from .models import WorkingChange
from uuid import uuid4


def create_person(db: Session, display_name: str, sex: str, notes: str | None, tree_id: int | None = None, tree_version_id: int | None = None):
    # Do not change per-record version automatically; tree_version_id identifies versioning
    p = Person(display_name=display_name, sex=Sex(sex), notes=notes, tree_id=tree_id, tree_version_id=tree_version_id)
    db.add(p); db.commit(); db.refresh(p)
    return p

def list_people(db: Session, tree_id: int | None = None, tree_version_id: int | None = None):
    q = db.query(Person)
    if tree_version_id is not None:
        q = q.filter(Person.tree_version_id == tree_version_id)
    elif tree_id is not None:
        # find active version for this tree
        tv = db.query(TreeVersion).filter(TreeVersion.tree_id == tree_id, TreeVersion.active == True).order_by(TreeVersion.version.desc()).first()
        if tv:
            q = q.filter(Person.tree_version_id == tv.id)
        else:
            q = q.filter(Person.tree_id == tree_id)
    return q.order_by(Person.display_name.asc()).all()

def create_relationship(db: Session, from_id: str, to_id: str | None, rel_type: str, tree_id: int | None = None, tree_version_id: int | None = None):
    rt = RelType(rel_type)

    if rt == RelType.EARLIEST_ANCESTOR:
        # enforce one root per tree/version
        existing_q = db.query(Relationship).filter(Relationship.type == RelType.EARLIEST_ANCESTOR)
        if tree_version_id is not None:
            existing_q = existing_q.filter(Relationship.tree_version_id == tree_version_id)
        elif tree_id is None:
            existing_q = existing_q.filter(Relationship.tree_id == None)
        else:
            existing_q = existing_q.filter(Relationship.tree_id == tree_id)
        existing = existing_q.first()
        if existing and existing.from_person_id != from_id:
            raise ValueError("An EARLIEST_ANCESTOR already exists for this tree. Remove it before setting a new one.")
        to_id = None

    if rt == RelType.CHILD_OF and not to_id:
        raise ValueError("to_person_id is required for CHILD_OF")

    # Do not set per-record version; use tree_version_id to scope versions
    r = Relationship(from_person_id=from_id, to_person_id=to_id, type=rt, tree_id=tree_id, tree_version_id=tree_version_id)
    db.add(r); db.commit(); db.refresh(r)
    return r


def create_draft(db: Session, tree_id: int | None, base_tree_version_id: int | None, change_type: str, payload: dict) -> WorkingChange:
    # For person drafts that create a new person, assign a stable draft_person_id so relationships can reference it
    if change_type == "person":
        # if editing an existing person, payload may include 'id' and we don't assign draft_person_id
        if not payload.get("id") and not payload.get("draft_person_id"):
            payload = dict(payload)
            payload["draft_person_id"] = str(uuid4())

    wc = WorkingChange(tree_id=tree_id, base_tree_version_id=base_tree_version_id, change_type=change_type, payload=payload)
    db.add(wc); db.commit(); db.refresh(wc)
    return wc


def list_drafts(db: Session, tree_id: int | None = None, base_tree_version_id: int | None = None) -> list[WorkingChange]:
    q = db.query(WorkingChange)
    if tree_id is not None:
        q = q.filter(WorkingChange.tree_id == tree_id)
    if base_tree_version_id is not None:
        q = q.filter(WorkingChange.base_tree_version_id == base_tree_version_id)
    return q.order_by(WorkingChange.created_at.asc()).all()


def delete_draft(db: Session, draft_id: int) -> None:
    d = db.query(WorkingChange).filter(WorkingChange.id == draft_id).first()
    if d:
        db.delete(d)
        db.commit()


def delete_drafts_for_base(db: Session, tree_id: int, base_tree_version_id: int) -> int:
    q = db.query(WorkingChange).filter(WorkingChange.tree_id == tree_id, WorkingChange.base_tree_version_id == base_tree_version_id)
    count = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    return count


def publish_drafts(db: Session, tree_id: int | None, base_tree_version_id: int | None) -> tuple[Tree, TreeVersion]:
    # create a new tree version
    tree = None
    if tree_id is not None:
        tree = db.query(Tree).filter(Tree.id == tree_id).first()
    tree, tv = create_or_increment_tree_version(db, name=(tree.name if tree else None), source_filename=None, tree_id=tree_id)

    # Build new snapshot by copying published data from base version (if any)
    old_to_new_person = {}
    if base_tree_version_id is not None:
        # copy persons from base version into new version
        base_people = db.query(Person).filter(Person.tree_version_id == base_tree_version_id).all()
        for p in base_people:
            newp = Person(display_name=p.display_name, sex=p.sex, notes=p.notes, tree_id=tree.id, tree_version_id=tv.id)
            db.add(newp)
            db.commit()
            db.refresh(newp)
            old_to_new_person[str(p.id)] = str(newp.id)

        # copy relationships from base version, remapping person ids
        base_rels = db.query(Relationship).filter(Relationship.tree_version_id == base_tree_version_id).all()
        for r in base_rels:
            from_id = old_to_new_person.get(str(r.from_person_id))
            to_id = old_to_new_person.get(str(r.to_person_id)) if r.to_person_id else None
            newr = Relationship(from_person_id=from_id or r.from_person_id, to_person_id=to_id or r.to_person_id, type=r.type, tree_id=tree.id, tree_version_id=tv.id)
            db.add(newr)
        db.commit()

    # Apply drafts on top of the copied snapshot
    drafts = db.query(WorkingChange).filter(WorkingChange.tree_id == tree.id, WorkingChange.base_tree_version_id == base_tree_version_id).order_by(WorkingChange.created_at.asc()).all()
    for d in drafts:
        if d.change_type == "person":
            payload = d.payload or {}
            # deletion of existing person
            if payload.get('id') and payload.get('deleted'):
                # find mapped id in new snapshot
                mapped = old_to_new_person.get(str(payload.get('id')))
                if mapped:
                    # delete any relationships referencing this person in new version
                    db.query(Relationship).filter(Relationship.tree_version_id == tv.id).filter((Relationship.from_person_id == mapped) | (Relationship.to_person_id == mapped)).delete(synchronize_session=False)
                    # delete the person row
                    db.query(Person).filter(Person.tree_version_id == tv.id, Person.id == mapped).delete(synchronize_session=False)
                # else nothing to do

            # edit existing person -> update copied person
            elif payload.get('id'):
                mapped = old_to_new_person.get(str(payload.get('id')))
                if mapped:
                    p = db.query(Person).filter(Person.tree_version_id == tv.id, Person.id == mapped).first()
                    if p:
                        if payload.get('display_name'):
                            p.display_name = payload.get('display_name')
                        if payload.get('sex'):
                            p.sex = payload.get('sex')
                        if payload.get('notes') is not None:
                            p.notes = payload.get('notes')
                        db.add(p); db.commit()
                # else: editing a person not in base snapshot – ignore

            else:
                # new draft person – create and register mapping from draft_person_id
                draft_pid = payload.get('draft_person_id') or f"draft-{d.id}"
                newp = Person(display_name=payload.get('display_name'), sex=(payload.get('sex') or 'U'), notes=payload.get('notes'), tree_id=tree.id, tree_version_id=tv.id)
                db.add(newp); db.commit(); db.refresh(newp)
                old_to_new_person[str(draft_pid)] = str(newp.id)

        elif d.change_type == "relationship":
            payload = d.payload or {}
            from_id = payload.get('from_person_id')
            to_id = payload.get('to_person_id')
            rel_type = payload.get('type')
            op = payload.get('op')

            # remap ids if they point to base-version persons or draft_person_ids
            mapped_from = old_to_new_person.get(str(from_id)) or from_id
            mapped_to = old_to_new_person.get(str(to_id)) if to_id is not None else None

            if op == 'replace' and mapped_from:
                # remove existing relationships for this child in the new version
                db.query(Relationship).filter(Relationship.tree_version_id == tv.id, Relationship.from_person_id == mapped_from).delete(synchronize_session=False)

            if op == 'delete' and mapped_from:
                # delete the specific relationship (child -> parent) in the new version
                q = db.query(Relationship).filter(Relationship.tree_version_id == tv.id, Relationship.from_person_id == mapped_from)
                if mapped_to is not None:
                    q = q.filter(Relationship.to_person_id == mapped_to)
                q.delete(synchronize_session=False)
                # do not create a new relationship
                continue

            # create new relationship (for 'create' or 'replace' semantics)
            r = Relationship(from_person_id=mapped_from, to_person_id=mapped_to, type=RelType(rel_type), tree_id=tree.id, tree_version_id=tv.id)
            db.add(r)

        # delete draft after applying
        db.delete(d)
    db.commit()
    return tree, tv


def create_or_increment_tree_version(db: Session, name: str | None = None, source_filename: str | None = None, tree_id: int | None = None) -> tuple[Tree, TreeVersion]:
    # Determine tree: by id if provided, else by name
    if tree_id is not None:
        tree = db.query(Tree).filter(Tree.id == tree_id).first()
        if not tree:
            raise ValueError(f"Tree id {tree_id} not found")
    else:
        if not name:
            # fallback name
            name = source_filename or "Imported"
        tree = db.query(Tree).filter(Tree.name == name).first()
        if not tree:
            tree = Tree(name=name, description=f"Imported from {source_filename or 'unknown'}")
            db.add(tree); db.commit(); db.refresh(tree)

    # compute next version
    last = db.query(TreeVersion).filter(TreeVersion.tree_id == tree.id).order_by(TreeVersion.version.desc()).first()
    next_ver = 1 if not last else (last.version + 1)

    # mark previous inactive
    if last:
        last.active = False
        db.add(last)

    tv = TreeVersion(tree_id=tree.id, version=next_ver, source_filename=source_filename, active=True)
    db.add(tv); db.commit(); db.refresh(tv)
    return tree, tv


def update_tree(db: Session, tree_id: int, name: str | None = None, description: str | None = None) -> Tree:
    t = db.query(Tree).filter(Tree.id == tree_id).first()
    if not t:
        raise ValueError(f"Tree id {tree_id} not found")
    if name is not None:
        t.name = name
    if description is not None:
        t.description = description
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

