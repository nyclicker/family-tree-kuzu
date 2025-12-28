from __future__ import annotations
from typing import Dict, List

def build_sibling_colors(
    nodes: List[str],
    children_map: Dict[str, List[str]],
    parents_map: Dict[str, List[str]],
    gender_map: Dict[str, str],
) -> List[str]:
    sibling_palette = [
        "#FFA07A", "#98FB98", "#87CEFA", "#DDA0DD", "#F4A460",
        "#66CDAA", "#FFB6C1", "#E6E6FA", "#20B2AA"
    ]

    parent_list = list(children_map.keys())
    parent_color_map = {p: sibling_palette[i % len(sibling_palette)] for i, p in enumerate(parent_list)}

    node_colors: List[str] = []
    for node in nodes:
        if node in parents_map and parents_map[node]:
            parent_id = parents_map[node][0]
            node_colors.append(parent_color_map.get(parent_id, "#D3D3D3"))
        else:
            g = (gender_map.get(node, "") or "").upper()
            if g == "M":
                node_colors.append("#87CEFA")
            elif g == "F":
                node_colors.append("#FFB6C1")
            else:
                node_colors.append("#D3D3D3")
    return node_colors
