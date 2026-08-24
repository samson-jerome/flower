from __future__ import annotations
from pathlib import Path
from flower.engine.execution.traversal import traverse
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node


def _escape(label: str) -> str:
    """A node name is free text; only the quote and the backslash can break
    a quoted DOT identifier."""
    return label.replace("\\", "\\\\").replace('"', '\\"')


def _render(nodes: list[Node]) -> str:
    """DOT text for `nodes`, numbered n1..nN in the order given, with an edge
    for every parent/child pair whose two ends are both in the list.

    Nodes are numbered rather than keyed by Node.id: xml_reader regenerates a
    uuid4 on every read, so ids would make the output differ on each export
    of an unchanged file. Names cannot serve as identifiers either -- nothing
    guarantees they are unique."""
    names = {node.id: f"n{i}" for i, node in enumerate(nodes, start=1)}
    lines = ["digraph flow {"]
    for node in nodes:
        lines.append(f'  {names[node.id]} [label="{_escape(node.name)}"];')
    for node in nodes:
        for child in node.children:
            if child.id in names:
                lines.append(f"  {names[node.id]} -> {names[child.id]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _all_nodes(nodes: list[Node]) -> list[Node]:
    result: list[Node] = []
    for node in nodes:
        result.append(node)
        result.extend(_all_nodes(node.children))
    return result


def to_dot(graph: Graph) -> str:
    """The whole graph's topology: one node per node, one edge per relation,
    in pre-order. No colour, shape or state -- it describes the file, and
    presentation belongs to the application layer."""
    return _render(_all_nodes(graph.roots))


def to_dot_active(graph: Graph) -> str:
    """Only what a run would execute: an inactive node disappears with its
    whole subtree. Defers to traverse(), the same walk the script generator
    uses, so "active" is defined in one place."""
    return _render(list(traverse(graph)))


def _write(text: str, path: Path) -> None:
    path.write_text(text, encoding="utf-8")


def write_dot(graph: Graph, path: Path) -> None:
    _write(to_dot(graph), path)


def write_dot_active(graph: Graph, path: Path) -> None:
    _write(to_dot_active(graph), path)
