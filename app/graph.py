from sqlalchemy.orm import Session
from .models import Person, Relationship, RelType
from .plotly_graph.plotly_render import build_plotly_figure_from_db
from .plotly_graph.legacy_io import LegacyRow

def build_graph(db: Session):
    people = {p.id: p for p in db.query(Person).all()}
    rels = db.query(Relationship).filter(Relationship.type.in_([RelType.CHILD_OF, RelType.EARLIEST_ANCESTOR])).all()

    # Create “legacy-like” rows
    # Legacy format: Person 1, Relation, Person 2, Gender, Details
    rows = []
    for r in rels:
        p1 = people.get(r.from_person_id)
        p2 = people.get(r.to_person_id)

        if not p1:
            continue

        if r.type == RelType.EARLIEST_ANCESTOR:
            rows.append({
                "person_1": p1.display_name,
                "relation": "Earliest Ancestor",
                "person_2": "",
                "gender": (p1.sex.value if p1.sex else "U"),
                "details": "Root",
            })
        elif r.type == RelType.CHILD_OF and p2:
            # Child -> Parent relationship
            rows.append({
                "person_1": p1.display_name,
                "relation": "Child",
                "person_2": p2.display_name,
                "gender": (p1.sex.value if p1.sex else "U"),
                "details": "",
            })

    fig = build_plotly_figure(rows, layer_gap=4.0)

    # Return Plotly JSON
    return fig.to_dict()

def _db_to_legacy_rows(db: Session) -> list[LegacyRow]:
    people = {p.id: p for p in db.query(Person).all()}
    rels = db.query(Relationship).all()

    rows: list[LegacyRow] = []

    # Earliest Ancestor -> row with person2 empty
    for r in rels:
        if r.type == RelType.EARLIEST_ANCESTOR:
            p1 = people.get(r.from_person_id)
            if p1:
                rows.append(
                    LegacyRow(
                        person1=p1.display_name,
                        relation="Earliest Ancestor",
                        person2="",
                        gender=(p1.sex.value if p1.sex else ""),
                        details="",
                    )
                )

    # Child relationships -> row where Person1 is child, Person2 is parent
    for r in rels:
        if r.type == RelType.CHILD_OF and r.to_person_id:
            child = people.get(r.from_person_id)
            parent = people.get(r.to_person_id)
            if child and parent:
                rows.append(
                    LegacyRow(
                        person1=child.display_name,
                        relation="Child",
                        person2=parent.display_name,
                        gender=(child.sex.value if child.sex else ""),
                        details="",
                    )
                )

    return rows

def build_plotly_figure_json(db: Session, layer_gap: float = 4.0) -> dict:
    people = db.query(Person).all()
    rels = db.query(Relationship).all()

    fig = build_plotly_figure_from_db(people, rels, layer_gap=layer_gap)
    return fig.to_dict()

"""
def build_plotly_graph_json(db: Session, layer_gap: float = 4.0) -> dict:
    rows = _db_to_legacy_rows(db)
    fig = build_plotly_figure(rows, layer_gap=layer_gap)
    # Return JSON for Plotly.newPlot(...)
    return fig.to_plotly_json()
"""