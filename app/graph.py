from sqlalchemy.orm import Session
from .models import Person, Relationship, RelType, WorkingChange
from .plotly_graph.plotly_render import build_plotly_figure_from_db
from types import SimpleNamespace

def build_plotly_figure_json(db: Session, tree_id: int | None = None, tree_version_id: int | None = None, layer_gap: float = 4.0) -> dict:
    q_people = db.query(Person)
    q_rels = db.query(Relationship)
    if tree_version_id is not None:
        q_people = q_people.filter(Person.tree_version_id == tree_version_id)
        q_rels = q_rels.filter(Relationship.tree_version_id == tree_version_id)
    elif tree_id is not None:
        q_people = q_people.filter(Person.tree_id == tree_id)
        q_rels = q_rels.filter(Relationship.tree_id == tree_id)

    people = q_people.all()
    rels = q_rels.all()

    # If tree and base version provided, include working drafts merged into the published data
    merged_people = {str(p.id): SimpleNamespace(id=str(p.id), display_name=p.display_name, sex=(p.sex if hasattr(p, 'sex') else None), is_draft=False) for p in people}
    merged_rels = []
    for r in rels:
        merged_rels.append(SimpleNamespace(id=str(r.id), from_person_id=str(r.from_person_id), to_person_id=str(r.to_person_id) if r.to_person_id else None, type=r.type))

    if tree_id is not None and tree_version_id is not None:
        drafts = db.query(WorkingChange).filter(WorkingChange.tree_id == tree_id, WorkingChange.base_tree_version_id == tree_version_id).order_by(WorkingChange.created_at.asc()).all()
        for d in drafts:
            payload = d.payload or {}
            if d.change_type == "person":
                # edit existing person
                if payload.get("id"):
                    pid = str(payload.get("id"))
                    if pid in merged_people:
                        # handle deletion
                        if payload.get("deleted"):
                            del merged_people[pid]
                            # also remove any relationships for this person
                            merged_rels = [rr for rr in merged_rels if rr.from_person_id != pid and rr.to_person_id != pid]
                            continue
                        if payload.get("display_name"):
                            merged_people[pid].display_name = payload.get("display_name")
                        if payload.get("sex"):
                            merged_people[pid].sex = payload.get("sex")
                else:
                    # new draft person
                    pid = payload.get("draft_person_id") or f"draft-person-{d.id}"
                    merged_people[str(pid)] = SimpleNamespace(id=str(pid), display_name=payload.get("display_name", "(draft)"), sex=payload.get("sex", None), is_draft=True)

            elif d.change_type == "relationship":
                # relationship payload expected to have from_person_id and to_person_id which may reference draft_person_id values
                from_id = payload.get("from_person_id")
                to_id = payload.get("to_person_id")
                rel_type = payload.get("type")
                op = payload.get('op')
                # if op == 'replace', remove existing merged_rels where from_person_id matches
                if op == 'replace' and from_id:
                    merged_rels = [rr for rr in merged_rels if rr.from_person_id != str(from_id)]

                # if op == 'delete', remove matching rels and do not append a new one
                if op == 'delete' and from_id:
                    merged_rels = [rr for rr in merged_rels if not (rr.from_person_id == str(from_id) and ((rr.to_person_id == str(to_id)) if to_id else (rr.to_person_id is None)))]
                    continue

                # otherwise append/create the draft relationship
                merged_rels.append(SimpleNamespace(id=f"draft-rel-{d.id}", from_person_id=str(from_id), to_person_id=str(to_id) if to_id else None, type=RelType(rel_type)))

    # build lists
    people_list = list(merged_people.values())
    rels_list = merged_rels

    # pass the set of published person ids so the renderer can correctly
    # identify draft-only nodes (UUID-based DB ids mean the old isdigit()
    # heuristic no longer works).
    published_ids = {str(p.id) for p in people}
    # If filtering by tree/version produced no published rows (older data may
    # not set `tree_version_id`), fall back to all known DB persons so draft
    # detection works robustly.
    if not published_ids:
        all_p = db.query(Person).all()
        published_ids = {str(p.id) for p in all_p}

    fig = build_plotly_figure_from_db(people_list, rels_list, published_ids=published_ids, layer_gap=layer_gap)
    # debug helper: expose published count for troubleshooting
    try:
        fig['layout']['published_ids_count'] = len(published_ids)
    except Exception:
        pass
    return fig.to_dict()