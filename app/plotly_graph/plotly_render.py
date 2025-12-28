from __future__ import annotations

from typing import Dict, List
from plotly import graph_objects as go
from fastapi.responses import JSONResponse
import json

from .legacy_io import LegacyRow
from .normalize import normalize_person
from .layout import radial_tree_layout_balanced_spaced
from .colors import build_sibling_colors


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


def build_plotly_figure(rows: List[LegacyRow], layer_gap: float = 4.0) -> go.Figure:
    children_map, parents_map, gender_map, display_name, hover_name, roots = build_maps(rows)

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


