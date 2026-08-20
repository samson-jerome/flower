from __future__ import annotations
from dataclasses import replace
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


def prune_to_node(graph: Graph, node_id: str) -> Graph:
    """Graph whose generated script stops right after the node identified by
    node_id: only that node's own root is kept (other roots are dropped), and
    inside it, only what precedes the target in pre-order plus the target
    itself, stripped of its subtree. Global variables and graph metadata are
    carried over unchanged.

    Feeds generate_bash_script() untouched: the generator sees a normal tree,
    so enclosing `fi`/`done` close as the recursion unwinds. Node copies share
    their `variables` list and `type_data` dict with the original -- the
    generator only reads them -- and the input graph is never mutated.

    is_active plays no part here: the generator already skips inactive nodes,
    exactly as it does for a full script.

    Raises ValueError if node_id is absent, which the UI never triggers: it
    only emits ids of nodes it just found in the model."""
    for root in graph.roots:
        pruned, found = _prune(root, node_id)
        if found:
            return replace(graph, roots=[pruned])
    raise ValueError(f"node {node_id!r} not found in graph")


def _prune(node: Node, node_id: str) -> tuple[Node, bool]:
    """Copy of `node` keeping only what precedes node_id in pre-order, plus
    node_id itself without its subtree. The flag says whether the target was
    found in this subtree; when False the copy is the whole subtree unchanged,
    and the caller drops it if the target turns up in an earlier sibling."""
    if node.id == node_id:
        return _copy(node, []), True
    children: list[Node] = []
    for child in node.children:
        pruned, found = _prune(child, node_id)
        children.append(pruned)
        if found:
            return _copy(node, children), True
    return _copy(node, children), False


def _copy(node: Node, children: list[Node]) -> Node:
    """Shallow copy of `node` with a new child list, parent links rebuilt on
    the copies so the pruned tree is self-consistent (the generator does not
    read `parent`, but a copy pointing back into the original tree would be a
    trap for any later caller)."""
    copy = replace(node, children=children)
    for child in children:
        child.parent = copy
    return copy
