from __future__ import annotations
from typing import Iterator
from flower.models.graph import Graph
from flower.models.node import Node


def traverse(graph: Graph) -> Iterator[Node]:
    """Yield nodes in execution order: pre-order (a node, then each of its
    children in list order, recursively), matching the visual top-left to
    bottom-right order already produced by layout/tree_layout.py's use of
    list order. A node with is_active=False and its whole subtree are
    skipped. is_collapsed has no effect (it is a UI-only state).
    """
    for root in graph.roots:
        yield from _traverse_node(root)


def _traverse_node(node: Node) -> Iterator[Node]:
    if not node.is_active:
        return
    yield node
    for child in node.children:
        yield from _traverse_node(child)
