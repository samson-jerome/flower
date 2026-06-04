from __future__ import annotations
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPainter, QKeyEvent, QFontMetrics, QFont
from PySide6.QtCore import Qt, Signal, QPoint
from flower.models.graph import Graph
from flower.models.node import Node
from flower.layout.tree_layout import compute_layout, NodePos
from flower.ui.node_item import NodeItem, NodeItemSignals
from flower.ui.edge_item import EdgeItem


def _deactivate_subtree(node: Node) -> None:
    for child in node.children:
        child.is_active = False
        _deactivate_subtree(child)


def _activate_ancestors(node: Node) -> None:
    parent = node.parent
    while parent is not None:
        parent.is_active = True
        parent = parent.parent


def _activate_subtree(node: Node) -> None:
    for child in node.children:
        child.is_active = True
        _activate_subtree(child)


class GraphCanvas(QGraphicsView):
    node_selected       = Signal(str)  # node_id
    node_edit_requested = Signal(str)  # node_id
    add_child_requested = Signal()
    delete_requested    = Signal()
    node_active_changed = Signal()     # graph mutated, mark dirty

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background: #1e1e1e;")

        self._graph:       Graph | None        = None
        self._items:       dict[str, NodeItem] = {}
        self._selected_id: str | None          = None
        self._space_held:  bool                = False
        self._pan_start:   QPoint              = QPoint()

        self._signals = NodeItemSignals()
        self._signals.selected.connect(self._on_node_selected)
        self._signals.edit_requested.connect(self.node_edit_requested)
        self._signals.active_toggled.connect(
            self._on_active_toggled, Qt.ConnectionType.QueuedConnection
        )
        self._signals.collapsed_toggled.connect(
            self._on_collapsed_toggled, Qt.ConnectionType.QueuedConnection
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def load_graph(self, graph: Graph) -> None:
        self._graph = graph
        self.refresh_layout()
        # Position view so first root node appears at top-left.
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def refresh_layout(self) -> None:
        if self._graph is None:
            return
        self._scene.clear()
        self._items.clear()
        fm = QFontMetrics(QFont())
        positions = compute_layout(self._graph.roots, fm.horizontalAdvance)
        self._draw(self._graph.roots, positions)
        self._update_scene_rect()

    def _update_scene_rect(self) -> None:
        """Limit pan to the bounding rect of all nodes (plus margin)."""
        rect = self._scene.itemsBoundingRect()
        if rect.isNull():
            return
        margin = 20.0
        self.setSceneRect(rect.adjusted(-margin, -margin, margin, margin))

    def select_node(self, node_id: str) -> None:
        for nid, item in self._items.items():
            item.set_selected(nid == node_id)
        self._selected_id = node_id
        self.node_selected.emit(node_id)

    def refresh_node(self, node: Node) -> None:
        if self._graph is None:
            return
        fm = QFontMetrics(QFont())
        positions = compute_layout(self._graph.roots, fm.horizontalAdvance)
        if node.id in self._items and node.id in positions:
            self._items[node.id].refresh(node, positions[node.id])

    # ── Drawing ─────────────────────────────────────────────────────────────

    def _draw(self, nodes: list[Node], positions: dict[str, NodePos]) -> None:
        for node in nodes:
            if node.id not in positions:
                continue
            item = NodeItem(node, positions[node.id], self._signals)
            self._scene.addItem(item)
            self._items[node.id] = item

            if not node.is_collapsed:
                for i, child in enumerate(node.children):
                    if child.id in positions:
                        edge = EdgeItem(
                            positions[node.id], positions[child.id],
                            child_index=i, parent_type=node.type,
                        )
                        self._scene.addItem(edge)
                self._draw(node.children, positions)

    # ── Events ──────────────────────────────────────────────────────────────

    def _on_node_selected(self, node_id: str) -> None:
        self.select_node(node_id)

    def _on_collapsed_toggled(self, node_id: str) -> None:
        node = self._find_node(node_id)
        if node is None:
            return
        node.is_collapsed = not node.is_collapsed
        prev_selected = self._selected_id
        self.refresh_layout()
        if prev_selected:
            self.select_node(prev_selected)
        self.node_active_changed.emit()

    def _on_active_toggled(self, node_id: str) -> None:
        node = self._find_node(node_id)
        if node is None:
            return
        node.is_active = not node.is_active
        if not node.is_active:
            _deactivate_subtree(node)
        else:
            _activate_ancestors(node)
            _activate_subtree(node)
        prev_selected = self._selected_id
        self.refresh_layout()
        if prev_selected:
            self.select_node(prev_selected)
        self.node_active_changed.emit()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.MiddleButton:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_held = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return
        self._handle_nav_key(event)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().keyReleaseEvent(event)

    def _handle_nav_key(self, event: QKeyEvent) -> None:
        if self._graph is None or self._selected_id is None:
            return
        node = self._find_node(self._selected_id)
        if node is None:
            return
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key.Key_Up and mod == Qt.KeyboardModifier.NoModifier:
            self._select_sibling(node, -1)
        elif key == Qt.Key.Key_Down and mod == Qt.KeyboardModifier.NoModifier:
            self._select_sibling(node, +1)
        elif key == Qt.Key.Key_Left:
            if node.parent:
                self.select_node(node.parent.id)
        elif key == Qt.Key.Key_Right:
            if node.children:
                self.select_node(node.children[0].id)
        elif key == Qt.Key.Key_Up and mod == Qt.KeyboardModifier.AltModifier:
            self._reorder_sibling(node, -1)
        elif key == Qt.Key.Key_Down and mod == Qt.KeyboardModifier.AltModifier:
            self._reorder_sibling(node, +1)
        elif key == Qt.Key.Key_R:
            self.refresh_layout()
        elif key == Qt.Key.Key_C:
            self.add_child_requested.emit()
        elif key == Qt.Key.Key_Delete:
            self.delete_requested.emit()

    def _find_node(self, node_id: str) -> Node | None:
        def _search(nodes: list[Node]) -> Node | None:
            for n in nodes:
                if n.id == node_id:
                    return n
                found = _search(n.children)
                if found:
                    return found
            return None
        return _search(self._graph.roots) if self._graph else None

    def _siblings(self, node: Node) -> list[Node]:
        return node.parent.children if node.parent else (self._graph.roots if self._graph else [])

    def _select_sibling(self, node: Node, delta: int) -> None:
        siblings = self._siblings(node)
        idx = next((i for i, n in enumerate(siblings) if n.id == node.id), None)
        if idx is not None and 0 <= idx + delta < len(siblings):
            self.select_node(siblings[idx + delta].id)

    def _reorder_sibling(self, node: Node, delta: int) -> None:
        siblings = self._siblings(node)
        idx = next((i for i, n in enumerate(siblings) if n.id == node.id), None)
        if idx is not None:
            new_idx = idx + delta
            if 0 <= new_idx < len(siblings):
                siblings[idx], siblings[new_idx] = siblings[new_idx], siblings[idx]
                self.refresh_layout()
