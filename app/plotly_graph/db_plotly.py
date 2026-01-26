from __future__ import annotations

from typing import Dict, List, Tuple
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from ..models import Person, Relationship, RelType


def _build_children_and_roots(
    people: List[Person],
    rels: List[Relationship],
) -> tuple[dict[str, list[str]], list[str], dict[str, list[str]]]:
    """
    Build children_map[parent_id] = [child_id, ...]
    spouse_map[person_id] = [spouse_id, ...]
    and discover roots.
    """
    person_ids = {p.id for p in people}

    children_map: Dict[str, List[str]] = {pid: [] for pid in person_ids}
    spouse_map: Dict[str, List[str]] = {pid: [] for pid in person_ids}
    child_ids: set[str] = set()

    explicit_roots: list[str] = []

    for r in rels:
        if r.type == RelType.CHILD_OF:
            # CHILD_OF means: from_person is the child, to_person is the parent
            child_id = r.from_person_id
            parent_id = r.to_person_id
            if parent_id in children_map:
                children_map[parent_id].append(child_id)
            child_ids.add(child_id)

        elif r.type == RelType.SPOUSE_OF:
            # SPOUSE_OF is bidirectional
            person1_id = r.from_person_id
            person2_id = r.to_person_id
            if person1_id in spouse_map and person2_id not in spouse_map[person1_id]:
                spouse_map[person1_id].append(person2_id)
            if person2_id in spouse_map and person1_id not in spouse_map[person2_id]:
                spouse_map[person2_id].append(person1_id)

        elif r.type == RelType.EARLIEST_ANCESTOR:
            # Treat "from_person" as an explicit root marker
            explicit_roots.append(r.from_person_id)

    # If explicit roots exist, use them; else infer roots = people who are not children of anyone
    if explicit_roots:
        roots = list(dict.fromkeys(explicit_roots))  # stable de-dupe
    else:
        roots = [p.id for p in people if p.id not in child_ids]

    return children_map, roots, spouse_map


def _simple_layer_layout(
    children_map: dict[str, list[str]],
    roots: list[str],
    spouse_map: dict[str, list[str]],
    layer_gap: float = 120.0,
    sibling_gap: float = 60.0,
    spouse_spacing: float = 40.0,
) -> dict[str, tuple[float, float]]:
    """
    Simple deterministic tree layout with spouse positioning:
    - y decreases with depth (top-down)
    - x spreads siblings
    - Spouses are placed side-by-side at the same Y level
    """
    pos: dict[str, tuple[float, float]] = {}
    positioned = set()

    # BFS by layers
    current = roots[:]
    depth = 0
    x_cursor = 0.0

    # Assign root positions left-to-right
    for ridx, rid in enumerate(current):
        pos[rid] = (x_cursor, -depth * layer_gap)
        positioned.add(rid)
        
        # Position spouses next to this root
        for spouse_id in spouse_map.get(rid, []):
            if spouse_id not in positioned:
                pos[spouse_id] = (x_cursor + spouse_spacing, -depth * layer_gap)
                positioned.add(spouse_id)
                current.append(spouse_id)  # Include spouse in processing
        
        x_cursor += sibling_gap * 2

    while current:
        next_level: list[str] = []
        depth += 1

        # Place children under each parent
        for parent_id in current:
            kids = children_map.get(parent_id, [])
            if not kids:
                continue

            px, _py = pos[parent_id]
            
            # If parent has a spouse, center children between them
            spouse_ids = spouse_map.get(parent_id, [])
            if spouse_ids and spouse_ids[0] in pos:
                spouse_x, _ = pos[spouse_ids[0]]
                center_x = (px + spouse_x) / 2.0
            else:
                center_x = px
            
            # Center children around parent x (or couple center)
            n = len(kids)
            start_x = center_x - (n - 1) * sibling_gap / 2.0
            for i, cid in enumerate(kids):
                if cid not in positioned:
                    child_x = start_x + i * sibling_gap
                    pos[cid] = (child_x, -depth * layer_gap)
                    positioned.add(cid)
                    
                    # Position child's spouse next to them
                    for child_spouse_id in spouse_map.get(cid, []):
                        if child_spouse_id not in positioned:
                            pos[child_spouse_id] = (child_x + spouse_spacing, -depth * layer_gap)
                            positioned.add(child_spouse_id)
                    
                    next_level.append(cid)

        current = next_level

    return pos


def build_plotly_figure_from_db(
    db: Session,
    layer_gap: float = 120.0,
) -> go.Figure:
    people = db.query(Person).all()
    rels = db.query(Relationship).all()

    # Map person_id -> label/hover/sex
    label: dict[str, str] = {p.id: p.display_name for p in people}
    sex: dict[str, str] = {p.id: (p.sex.value if p.sex else "U") for p in people}

    children_map, roots, spouse_map = _build_children_and_roots(people, rels)
    pos = _simple_layer_layout(children_map, roots, spouse_map, layer_gap=layer_gap)

    # Build parent-child edge segments using DB IDs
    edge_x: list[float] = []
    edge_y: list[float] = []
    edge_cd: list[dict] = []

    for r in rels:
        if r.type != RelType.CHILD_OF:
            continue
        child_id = r.from_person_id
        parent_id = r.to_person_id
        if parent_id not in pos or child_id not in pos:
            continue

        x0, y0 = pos[parent_id]
        x1, y1 = pos[child_id]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_cd += [
            {"relationship_id": r.id, "parent_id": parent_id, "child_id": child_id},
            {"relationship_id": r.id, "parent_id": parent_id, "child_id": child_id},
            None,
        ]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="text",
        hovertext=["Parent-Child" if cd else "" for cd in edge_cd],
        hoverdistance=48,
        line=dict(width=2, color="#555"),
        showlegend=False,
        customdata=edge_cd,
    )

    # Build spouse edge segments (horizontal lines)
    spouse_x: list[float] = []
    spouse_y: list[float] = []
    spouse_cd: list[dict] = []

    for r in rels:
        if r.type != RelType.SPOUSE_OF:
            continue
        person1_id = r.from_person_id
        person2_id = r.to_person_id
        if person1_id not in pos or person2_id not in pos:
            continue

        x0, y0 = pos[person1_id]
        x1, y1 = pos[person2_id]
        spouse_x += [x0, x1, None]
        spouse_y += [y0, y1, None]
        spouse_cd += [
            {"relationship_id": r.id, "spouse1_id": person1_id, "spouse2_id": person2_id},
            {"relationship_id": r.id, "spouse1_id": person1_id, "spouse2_id": person2_id},
            None,
        ]

    spouse_trace = go.Scatter(
        x=spouse_x,
        y=spouse_y,
        mode="lines",
        hoverinfo="text",
        hovertext=["Spouse" if cd else "" for cd in spouse_cd],
        hoverdistance=48,
        line=dict(width=2, color="#E91E63", dash="dot"),  # Pink dashed line for spouses
        showlegend=False,
        customdata=spouse_cd,
    )

    # Node scatter (again keyed by DB ids)
    node_ids = [pid for pid in pos.keys()]
    node_x = [pos[pid][0] for pid in node_ids]
    node_y = [pos[pid][1] for pid in node_ids]
    node_text = [label.get(pid, pid) for pid in node_ids]
    node_hover = [f"{label.get(pid, pid)}<br>ID: {pid}<br>Sex: {sex.get(pid,'U')}" for pid in node_ids]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        hovertext=node_hover,
        hoverinfo="text",
        textposition="middle center",
        customdata=node_ids,  # <-- THIS is the key improvement: DB IDs carried in the figure
    )

    fig = go.Figure(data=[edge_trace, spouse_trace, node_trace])
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig
