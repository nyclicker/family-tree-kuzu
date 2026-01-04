from __future__ import annotations

from typing import Dict, List, Tuple
from plotly import graph_objects as go
from fastapi.responses import JSONResponse
import json
from .legacy_io import LegacyRow
from .normalize import normalize_person
from .layout import radial_tree_layout_balanced_spaced
from .colors import build_sibling_colors
from app.models import Person, Relationship, RelType

def build_maps(rows: List[LegacyRow]):
    children_map: Dict[str, List[str]] = {}
    parents_map: Dict[str, List[str]] = {}
    gender_map: Dict[str, str] = {}
    display_name: Dict[str, str] = {}
    hover_name: Dict[str, str] = {}
    explicit_roots: List[str] = []

    for row in rows:
        rel = (row.relation or "").strip()

        p1_id, p1_disp, p1_hover = normalize_person(row.person1)
        p2_id, p2_disp, p2_hover = normalize_person(row.person2)

        gender = (row.gender or "").strip()

        if not p1_id:
            continue

        if p1_disp and p1_id not in display_name:
            display_name[p1_id] = p1_disp
        if p1_hover and p1_id not in hover_name:
            hover_name[p1_id] = p1_hover

        if p2_id:
            if p2_disp and p2_id not in display_name:
                display_name[p2_id] = p2_disp
            if p2_hover and p2_id not in hover_name:
                hover_name[p2_id] = p2_hover

        if gender and gender.lower() != "nan":
            gender_map[p1_id] = gender.upper()

        if rel == "Earliest Ancestor":
            explicit_roots.append(p1_id)

        if rel == "Child" and p2_id:
            children_map.setdefault(p2_id, []).append(p1_id)
            parents_map.setdefault(p1_id, []).append(p2_id)

    if explicit_roots:
        seen = set()
        roots = []
        for r in explicit_roots:
            if r not in seen:
                seen.add(r)
                roots.append(r)
    else:
        all_ids = set(display_name.keys()) | set(children_map.keys())
        child_ids = set(parents_map.keys())
        roots = list(all_ids - child_ids)

    # ensure everyone appears
    for person_id in list(display_name.keys()):
        children_map.setdefault(person_id, [])
        parents_map.setdefault(person_id, parents_map.get(person_id, []))

    return children_map, parents_map, gender_map, display_name, hover_name, roots

# Main Graph Builder Code
def build_plotly_figure_from_db(people: List[Person], rels: List[Relationship], layer_gap: float = 4.0) -> go.Figure:
    children_map, parents_map, gender_map, display_name, hover_name, roots = build_maps_from_db(people, rels)

    if not roots:
        fig = go.Figure()
        fig.update_layout(title="No family data found")
        return fig

    # Debug if we're using IDs
    # sanity checks
    print("DEBUG: Checking IDs...")
    assert all(isinstance(k, str) for k in children_map.keys())
    for p, kids in children_map.items():
        for c in kids:
            assert isinstance(c, str)

    # do all ids referenced by rels exist in people?
    people_ids = {str(p.id) for p in people}
    dangling = []
    for parent, kids in children_map.items():
        if parent not in people_ids:
            dangling.append(("parent", parent))
        for child in kids:
            if child not in people_ids:
                dangling.append(("child", child))

    if dangling:
        print("DANGLING IDS:", dangling[:20])

    print("DEBUG: ID checks passed.")
    # End Debug Code

    pos = radial_tree_layout_balanced_spaced(children_map, roots, layer_gap=layer_gap)

    # --- OPTIONAL: index relationships by (parent_id, child_id) so edges can carry rel IDs
    rel_id_by_pair = {}
    for r in rels:
        # If your rels are CHILD_OF (child -> parent)
        if str(r.type) == "RelType.CHILD_OF" or getattr(r.type, "value", None) == "CHILD_OF":
            child_id = r.from_person_id
            parent_id = r.to_person_id
            rel_id_by_pair[(parent_id, child_id)] = r.id

    edge_x, edge_y = [], []
    edge_customdata = []  # <-- NEW: rel metadata aligned to segments

    for parent_id, kids in children_map.items():
        for child_id in kids:
            if parent_id in pos and child_id in pos:
                x0, y0 = pos[parent_id]
                x1, y1 = pos[child_id]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

                # one entry per point (including the None break) so it stays aligned
                rid = rel_id_by_pair.get((parent_id, child_id))
                edge_customdata += [
                    {"relationship_id": rid, "parent_id": parent_id, "child_id": child_id},
                    {"relationship_id": rid, "parent_id": parent_id, "child_id": child_id},
                    None,
                ]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=1, color="gray"),
        hoverinfo="none",
        customdata=edge_customdata,  # <-- NEW (optional)
    )

    nodes = list(pos.keys())  # these are person_ids
    node_colors = build_sibling_colors(nodes, children_map, parents_map, gender_map)

    node_x, node_y, texts, hover_texts, node_customdata = [], [], [], [], []  # <-- NEW

    for person_id in nodes:
        x, y = pos[person_id]
        node_x.append(x)
        node_y.append(y)

        # UI label still uses name
        short_label = display_name.get(person_id, person_id).replace("\n", "<br>")
        texts.append(short_label)

        hover_label = hover_name.get(person_id, short_label).replace("\n", "<br>")
        hover_texts.append(hover_label)

        # <-- NEW: attach IDs (and anything else you want)
        node_customdata.append({
            "person_id": person_id,
            "label": display_name.get(person_id, None),
        })

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=texts,                       # what user sees
        textposition="top center",
        hoverinfo="text",
        hovertext=hover_texts,            # what user sees on hover
        customdata=node_customdata,       # <-- NEW: your true IDs live here
        marker=dict(size=18, color=node_colors, line=dict(width=1, color="#333")),
        textfont=dict(size=9),
    )

    fig = go.Figure(data=[edge_trace, node_trace])

    # compute bounds from your node positions (pos: dict[node_id] -> (x,y))
    xs = [xy[0] for xy in pos.values()]
    ys = [xy[1] for xy in pos.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad_x = 0.15 * (x_max - x_min if x_max > x_min else 1)
    pad_y = 0.15 * (y_max - y_min if y_max > y_min else 1)

    fig.update_layout(
        # keep your click interaction
        clickmode="event+select",

        showlegend=False,
        hovermode="closest",

        # interaction defaults
        dragmode="pan",          # drag pans; wheel zoom still works
        # uirevision=True,        # optional: preserves zoom state across figure updates

        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",

        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[x_min - pad_x, x_max + pad_x],
            scaleanchor="y",
            scaleratio=1,
            fixedrange=False,     # ensure zoom is allowed
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[y_min - pad_y, y_max + pad_y],
            fixedrange=False,     # ensure zoom is allowed
        ),
    )
    return fig


def build_maps_from_db(
    people: List[Person],
    rels: List[Relationship],
) -> Tuple[
    Dict[str, List[str]],  # children_map (parent_id -> [child_id])
    Dict[str, List[str]],  # parents_map  (child_id  -> [parent_id])
    Dict[str, str],        # gender_map   (person_id -> "M"/"F"/"U")
    Dict[str, str],        # display_name (person_id -> label)
    Dict[str, str],        # hover_name   (person_id -> hover label)
    List[str],             # roots        ([root_id])
]:
    children_map: Dict[str, List[str]] = {}
    parents_map: Dict[str, List[str]] = {}
    gender_map: Dict[str, str] = {}
    display_name: Dict[str, str] = {}
    hover_name: Dict[str, str] = {}

    # people maps
    for p in people:
        pid = str(p.id)
        display_name[pid] = p.display_name or pid
        hover_name[pid] = (p.display_name or pid)
        if getattr(p, "sex", None):
            gender_map[pid] = str(p.sex.value) if hasattr(p.sex, "value") else str(p.sex)

    # relationships
    explicit_roots: List[str] = []
    for r in rels:
        a = str(r.from_person_id)
        b = str(r.to_person_id)

        if r.type == RelType.EARLIEST_ANCESTOR:
            # convention: from_person is the root; to_person can be ignored or set to self
            explicit_roots.append(a)

        elif r.type == RelType.CHILD_OF:
            # convention: from_person is the child, to_person is the parent
            child_id, parent_id = a, b
            children_map.setdefault(parent_id, []).append(child_id)
            parents_map.setdefault(child_id, []).append(parent_id)

    # pick roots
    roots = explicit_roots[:]

    # if no explicit roots, infer: nodes with no parents
    if not roots:
        all_ids = {str(p.id) for p in people}
        child_ids = set(parents_map.keys())
        roots = sorted(list(all_ids - child_ids))

    return children_map, parents_map, gender_map, display_name, hover_name, roots


"""
def build_plotly_figure_from_db(people: List[Person], rels: List[Relationship], layer_gap: float = 4.0) -> go.Figure:
    children_map, parents_map, gender_map, display_name, hover_name, roots = build_maps_from_db(people, rels)

    if not roots:
        fig = go.Figure()
        fig.update_layout(title="No family data found")
        return fig

    pos = radial_tree_layout_balanced_spaced(children_map, roots, layer_gap=layer_gap)

    edge_x, edge_y = [], []
    for parent, kids in children_map.items():
        for child in kids:
            if parent in pos and child in pos:
                x0, y0 = pos[parent]
                x1, y1 = pos[child]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=1, color="gray"),
        hoverinfo="none",
    )

    nodes = list(pos.keys())
    node_colors = build_sibling_colors(nodes, children_map, parents_map, gender_map)

    node_x, node_y, texts, hover_texts = [], [], [], []
    for n in nodes:
        x, y = pos[n]
        node_x.append(x)
        node_y.append(y)

        short_label = display_name.get(n, str(n)).replace("\n", "<br>")
        texts.append(short_label)

        hover_label = hover_name.get(n, str(n)).replace("\n", "<br>")
        hover_texts.append(hover_label)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=texts,
        textposition="top center",
        hoverinfo="text",
        hovertext=hover_texts,
        marker=dict(size=18, color=node_colors, line=dict(width=1, color="#333")),
        textfont=dict(size=9),
    )

    xs = [xy[0] for xy in pos.values()]
    ys = [xy[1] for xy in pos.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad_x = 0.15 * (x_max - x_min if x_max > x_min else 1)
    pad_y = 0.15 * (y_max - y_min if y_max > y_min else 1)

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        dragmode="pan",
        autosize=True,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[x_min - pad_x, x_max + pad_x],
            scaleanchor="y",
            scaleratio=1,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[y_min - pad_y, y_max + pad_y],
        ),
    )
    return fig


def write_html(fig: go.Figure, out_path: str) -> None:
    config = {"scrollZoom": True, "displayModeBar": True, "responsive": True}
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True, config=config)

def build_maps_from_db(
    people: List[Person],
    rels: List[Relationship],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, str], Dict[str, str], Dict[str, str], List[str]]:
    children_map: Dict[str, List[str]] = {}
    parents_map: Dict[str, List[str]] = {}
    gender_map: Dict[str, str] = {}
    display_name: Dict[str, str] = {}
    hover_name: Dict[str, str] = {}
    roots: List[str] = []

    # People: keyed by person.id
    for p in people:
        display_name[p.id] = p.display_name
        hover_name[p.id] = p.display_name  # or richer hover later
        gender_map[p.id] = (p.sex.value if p.sex else "U")

    # Relationships: use ids directly
    for r in rels:
        if r.type == RelType.CHILD_OF:
            # child = from_person_id, parent = to_person_id
            children_map.setdefault(r.to_person_id, []).append(r.from_person_id)
            parents_map.setdefault(r.from_person_id, []).append(r.to_person_id)

        elif r.type == RelType.EARLIEST_ANCESTOR:
            # simplest convention: root stored as self-link (from == to)
            roots.append(r.from_person_id)

    return children_map, parents_map, gender_map, display_name, hover_name, roots

"""