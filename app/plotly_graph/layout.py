from __future__ import annotations
import math
from typing import Dict, List, Tuple

def radial_tree_layout_balanced_spaced(
    children_map: Dict[str, List[str]],
    roots: List[str],
    layer_gap: float = 4.0,
    radial_scale: float = 0.18,
    child_padding: float = 0.03,
    depth_padding_scale: float = 0.5,
) -> Dict[str, Tuple[float, float]]:
    """
    Balanced radial layout with depth-aware sibling padding.
    - Supports multiple roots via a virtual root.
    - Angles allocated proportional to subtree size.
    """
    roots = [r for r in roots if r]
    if not roots:
        return {}

    use_virtual_root = len(roots) > 1
    VROOT = "__VIRTUAL_ROOT__"

    local_children = {p: list(kids) for p, kids in children_map.items()}
    if use_virtual_root:
        local_children[VROOT] = roots.copy()
        root_for_layout = VROOT
    else:
        root_for_layout = roots[0]
        local_children.setdefault(root_for_layout, [])

    # ensure every node appears
    all_nodes = set(local_children.keys())
    for kids in local_children.values():
        all_nodes.update(kids)
    for n in all_nodes:
        local_children.setdefault(n, [])

    # subtree sizes
    subtree_cache: Dict[str, int] = {}

    def subtree_size(node: str) -> int:
        if node in subtree_cache:
            return subtree_cache[node]
        size = 1
        for c in local_children.get(node, []):
            size += subtree_size(c)
        subtree_cache[node] = size
        return size

    for n in all_nodes:
        subtree_size(n)

    def effective_radius(depth: int) -> float:
        if depth == 0:
            return 0.0
        return depth * layer_gap * (1.0 + radial_scale * max(depth - 1, 0))

    pos: Dict[str, Tuple[float, float]] = {}

    def assign(node: str, depth: int, a0: float, a1: float):
        amid = 0.5 * (a0 + a1)
        r = effective_radius(depth)

        if node != VROOT:
            pos[node] = (r * math.cos(amid), r * math.sin(amid))

        kids = local_children.get(node, [])
        if not kids:
            return

        sizes = [subtree_cache[k] for k in kids]
        total = sum(sizes)
        if total <= 0:
            return

        n = len(kids)
        eff_pad = child_padding * (1.0 + depth_padding_scale * max(depth - 1, 0))
        total_pad = eff_pad * max(n - 1, 0)

        span = a1 - a0
        usable = max(span - total_pad, span * 0.3)

        cur = a0
        for kid, s in zip(kids, sizes):
            share = s / total
            kspan = usable * share
            assign(kid, depth + 1, cur, cur + kspan)
            cur = cur + kspan + eff_pad

    assign(root_for_layout, 0, 0.0, 2.0 * math.pi)
    return pos
