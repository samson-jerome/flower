from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from flower.engine.io.xml_reader import read_flow
from flower.engine.io.xml_writer import write_flow
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node


class FlowGraph:
    """One .flow file: its graph, and every operation on it.

    The only public entry point of the engine. Holds the modified flag so no
    caller has to remember to raise it, and is the only module of the engine
    allowed to read the clock (see save() and write_run_script()).

    Structural changes -- a node's existence, its relations, its states --
    go through these methods. A node's own content (name aside, plus
    description, notes, variables, type_data) stays edited in place by the
    presentation layer, which then calls mark_modified().
    """

    def __init__(self, graph: Graph, path: Path | None = None):
        self.graph    = graph
        self.path     = path
        self.is_dirty = False

    # ── File lifecycle ──────────────────────────────────────────────────────

    @classmethod
    def new(cls) -> FlowGraph:
        return cls(Graph())

    @classmethod
    def open(cls, path: Path) -> FlowGraph:
        return cls(read_flow(path), path)

    def save(self, path: Path | None = None) -> None:
        """Write the graph, stamping updated_at. `path` becomes the flow's
        path when given (Save As); without one, a flow that never had a path
        raises rather than guessing a filename.

        Nothing is committed to the object until the write succeeds: a failed
        write leaves the flow exactly as it was -- still dirty, still pointing
        at its previous path, still carrying its previous updated_at. Stamping
        has to happen before the write, since the value travels into the file,
        hence the snapshot. The catch is deliberately broad: write_flow() can
        fail on the disk (OSError) as well as during serialization, before a
        single byte is written (lxml raises ValueError/TypeError on content
        that is not XML-compatible) -- either way, no write happened, so the
        snapshot must be restored the same way."""
        target = path if path is not None else self.path
        if target is None:
            raise ValueError("this flow has no path: pass one to save()")
        previous_updated_at = self.graph.updated_at
        self.graph.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            write_flow(self.graph, target)
        except Exception:
            self.graph.updated_at = previous_updated_at
            raise
        self.path     = target
        self.is_dirty = False

    # ── Access ──────────────────────────────────────────────────────────────

    def _walk(self, nodes: list[Node] | None = None) -> Iterator[Node]:
        for node in self.graph.roots if nodes is None else nodes:
            yield node
            yield from self._walk(node.children)

    def find(self, node_id: str) -> Node | None:
        return next((n for n in self._walk() if n.id == node_id), None)

    def _require(self, node_id: str) -> Node:
        """The node, or ValueError -- what every mutation calls, so an id the
        caller invented never mutates a neighbouring node silently."""
        node = self.find(node_id)
        if node is None:
            raise ValueError(f"node {node_id!r} not found in graph")
        return node

    def unique_name(self, base: str) -> str:
        """`base` if no node bears it, else base_1, base_2... Only new nodes
        get a unique name; renaming does not enforce uniqueness, so duplicate
        names can exist and this must skip taken suffixes."""
        existing = {n.name for n in self._walk()}
        if base not in existing:
            return base
        i = 1
        while f"{base}_{i}" in existing:
            i += 1
        return f"{base}_{i}"

    # ── Modified flag ───────────────────────────────────────────────────────

    def mark_modified(self) -> None:
        self.is_dirty = True
