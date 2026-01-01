from __future__ import annotations

from typing import Dict, List, Tuple
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from ..models import Person, Relationship, RelType


def _build_children_and_roots(
    people: List[Person],
    rels: List[Relationship],
) -> tuple[dict[str, list[str]], list[str]]:
    """
    Build children_map[parent_id] = [child_id, ...]
    and discover roots.
    """
    person_ids = {p.id for p in people}

    children_map: Dict[str, List[str]] = {pid: [] for pid in person_ids}
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

        elif r.type == RelType.EARLIEST_ANCESTOR:
            # Treat "from_person" as an explicit root marker
            explicit_roots.append(r.from_person_id)

    # If explicit roots exist, use them; else infer roots = people who are not children of anyone
    if explicit_roots:
        roots = list(dict.fromkeys(explicit_roots))  # stable de-dupe
    else:
        roots = [p.id for p in people if p.id not in child_ids]

    return children_map, roots


def _simple_layer_layout(
    children_map: dict[str, list[str]],
    roots: list[str],
    layer_gap: float = 120.0,
    sibling_gap: float = 60.0,
) -> dict[str, tuple[float, float]]:
    """
    Simple deterministic tree layout:
    - y decreases with depth (top-down)
    - x spreads siblings
    If you already have a nicer layout function, plug it in here.
    """
    pos: dict[str, tuple[float, float]] = {}

    # BFS by layers
    current = roots[:]
    depth = 0
    x_cursor = 0.0

    # Assign root positions left-to-right
    for ridx, rid in enumerate(current):
        pos[rid] = (x_cursor, -depth * layer_gap)
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
            # Center children around parent x
            n = len(kids)
            start_x = px - (n - 1) * sibling_gap / 2.0
            for i, cid in enumerate(kids):
                if cid not in pos:
                    pos[cid] = (start_x + i * sibling_gap, -depth * layer_gap)
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

    children_map, roots = _build_children_and_roots(people, rels)
    pos = _simple_layer_layout(children_map, roots, layer_gap=layer_gap)

    # Build edge segments using DB IDs (no name-based linking)
    edge_x: list[float] = []
    edge_y: list[float] = []

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

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="skip",
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

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig
