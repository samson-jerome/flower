from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from flower.engine.errors import CycleError, MaxChildrenError
from flower.engine.io.xml_reader import read_flow
from flower.engine.io.xml_writer import write_flow
from flower.engine.models.graph import Graph
from flower.engine.models.node import MAX_CHILDREN, Node, NodeType


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

    # ── Structural mutations ────────────────────────────────────────────────

    def add_node(
        self, parent_id: str | None, type: NodeType = NodeType.NOOP,
        name: str | None = None,
    ) -> Node:
        """Append a new node under `parent_id`, or as a new root when it is
        None. `name` is made unique; omitting it falls back to "nouveau", the
        name the toolbar and the canvas shortcut have always used."""
        parent = self._require(parent_id) if parent_id is not None else None
        if parent is not None:
            self._check_capacity(parent)
        node = Node(
            id=str(uuid.uuid4()),
            name=self.unique_name(name if name is not None else "nouveau"),
            type=type,
        )
        self._attach(node, parent)
        self.mark_modified()
        return node

    def remove_node(self, node_id: str) -> None:
        """Detach the node, and with it its whole subtree."""
        self._detach(self._require(node_id))
        self.mark_modified()

    def reparent(
        self, node_id: str, new_parent_id: str | None, index: int | None = None
    ) -> None:
        """Move the node -- and its subtree -- under `new_parent_id`, or to
        the roots when it is None. `index` defaults to last child, which is
        what dropping on the canvas does.

        Raises CycleError when the target is the node itself or one of its
        descendants, and MaxChildrenError when the target type is full."""
        node   = self._require(node_id)
        parent = self._require(new_parent_id) if new_parent_id is not None else None
        if parent is not None:
            if parent is node or self._is_descendant_of(parent, node):
                raise CycleError(node_id)
            self._check_capacity(parent)
        self._detach(node)
        self._attach(node, parent, index)
        self.mark_modified()

    def reorder(self, node_id: str, delta: int) -> None:
        """Swap the node with the sibling `delta` positions away. A move past
        either end is a no-op and leaves the flow clean -- moving the first
        sibling up changes nothing, so nothing was modified."""
        node     = self._require(node_id)
        siblings = self._siblings(node)
        index    = siblings.index(node)
        target   = index + delta
        if not 0 <= target < len(siblings):
            return
        siblings[index], siblings[target] = siblings[target], siblings[index]
        self.mark_modified()

    def rename_node(self, node_id: str, name: str) -> None:
        self._require(node_id).name = name
        self.mark_modified()

    def set_active(self, node_id: str, value: bool) -> None:
        """Deactivating carries the whole subtree down with it, since the
        generator skips an inactive node's descendants anyway. Activating
        carries the subtree up and reactivates the ancestor chain, so the
        node is really reached at execution time."""
        node = self._require(node_id)
        node.is_active = value
        self._set_subtree_active(node, value)
        if value:
            self._activate_ancestors(node)
        self.mark_modified()

    def set_collapsed(self, node_id: str, value: bool) -> None:
        """Marks the flow modified: is_collapsed is persisted in the .flow
        (the `collapsed` attribute), unlike a purely visual state."""
        self._require(node_id).is_collapsed = value
        self.mark_modified()

    def set_executable(self, node_id: str, value: bool) -> None:
        self._require(node_id).is_executable = value
        self.mark_modified()

    # ── Mutation helpers ────────────────────────────────────────────────────

    def _siblings(self, node: Node) -> list[Node]:
        return node.parent.children if node.parent is not None else self.graph.roots

    def _check_capacity(self, parent: Node) -> None:
        max_children = MAX_CHILDREN.get(parent.type)
        if max_children is not None and len(parent.children) >= max_children:
            raise MaxChildrenError(parent.type, max_children)

    def _attach(self, node: Node, parent: Node | None, index: int | None = None) -> None:
        node.parent = parent
        siblings    = parent.children if parent is not None else self.graph.roots
        if index is None:
            siblings.append(node)
        else:
            siblings.insert(index, node)

    def _detach(self, node: Node) -> None:
        self._siblings(node).remove(node)

    def _is_descendant_of(self, node: Node, ancestor: Node) -> bool:
        current = node.parent
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False

    def _set_subtree_active(self, node: Node, value: bool) -> None:
        for child in node.children:
            child.is_active = value
            self._set_subtree_active(child, value)

    def _activate_ancestors(self, node: Node) -> None:
        parent = node.parent
        while parent is not None:
            parent.is_active = True
            parent = parent.parent

    # ── Modified flag ───────────────────────────────────────────────────────

    def mark_modified(self) -> None:
        self.is_dirty = True
