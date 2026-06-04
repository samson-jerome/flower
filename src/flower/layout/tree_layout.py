from __future__ import annotations
from typing import Callable, NamedTuple
from flower.models.node import Node, NodeType

NODE_STEP      = 44.0
NODE_PADDING_H = 24.0
MIN_NODE_WIDTH = 120.0
MAX_NODE_WIDTH = 300.0
NODE_GAP_H     = 20.0  # horizontal gap between a parent column and its children column


class NodePos(NamedTuple):
    x:     float
    y:     float
    width: float


def node_label(node: Node) -> str:
    t = node.type
    d = node.type_data
    if t == NodeType.SCRIPT:
        lang = d.get("language", "")
        return f"{node.name} [{lang}]" if lang else node.name
    if t == NodeType.IF:
        cond = d.get("condition", "")
        return f"{node.name} : {cond[:30]}" if cond else node.name
    if t == NodeType.LOOP:
        idx  = d.get("index", "")
        mode = d.get("mode", "range")
        if mode == "range":
            return f"{node.name} [{idx}: {d.get('start', 0)}..{d.get('end', 0)}]"
        return f"{node.name} [{idx}: list]"
    return node.name


def _collect_widths(node: Node, depth: int, width_fn: Callable[[str], float], widths: dict[int, float]) -> None:
    label = node_label(node)
    w = min(MAX_NODE_WIDTH, max(MIN_NODE_WIDTH, width_fn(label) + NODE_PADDING_H))
    widths[depth] = max(widths.get(depth, 0.0), w)
    for child in node.children:
        _collect_widths(child, depth + 1, width_fn, widths)


def _place(
    node: Node,
    depth: int,
    y_start: float,
    col_x: dict[int, float],
    widths: dict[int, float],
    positions: dict[str, NodePos],
) -> float:
    w = widths.get(depth, MIN_NODE_WIDTH)
    positions[node.id] = NodePos(x=col_x.get(depth, 0.0), y=y_start, width=w)
    if not node.children:
        return y_start + NODE_STEP
    # First child starts at the same Y as the parent.
    y = y_start
    for child in node.children:
        y = _place(child, depth + 1, y, col_x, widths, positions)
    return y


def compute_layout(roots: list[Node], width_fn: Callable[[str], float]) -> dict[str, NodePos]:
    widths: dict[int, float] = {}
    for root in roots:
        _collect_widths(root, 0, width_fn, widths)

    col_x: dict[int, float] = {}
    x = 0.0
    for d in range(max(widths.keys()) + 1 if widths else 0):
        col_x[d] = x
        x += widths.get(d, MIN_NODE_WIDTH) + NODE_GAP_H

    positions: dict[str, NodePos] = {}
    y = 0.0
    for root in roots:
        y = _place(root, 0, y, col_x, widths, positions)

    return positions
