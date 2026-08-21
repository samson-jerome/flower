from __future__ import annotations
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QApplication
from PySide6.QtGui import QPainter, QKeyEvent, QFontMetrics, QFont, QPixmap, QColor, QPen, QBrush, QPainterPath
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QRectF
from flower.engine.api import FlowGraph
from flower.engine.errors import GraphRuleError
from flower.engine.models.node import Node
from flower.app.layout.tree_layout import compute_layout, NodePos, node_label
from flower.app.node_item import NodeItem, NodeItemSignals, NodeZone, NODE_HEIGHT, _TYPE_COLORS
from flower.app.edge_item import EdgeItem
from flower.app.messages import rule_message
from flower.app.prefs.theme import is_dark

_CANVAS_BG_DARK  = "#1e1e1e"
_CANVAS_BG_LIGHT = "#e3e3e3"

_DRAG_GHOST_W       = 180
_DRAG_GHOST_MAX     = 4    # node + up to 3 children shown
_DRAG_GHOST_OFFSET = 14   # px offset of ghost from cursor
_GHOST_MAX_W       = 600
_GHOST_MAX_H       = 400


def _create_drag_pixmap_from_layout(drag_node: Node, items: dict, dark: bool) -> QPixmap:
    """Render the dragged subtree preserving its actual layout positions."""

    def collect_visible(node: Node, result: list) -> None:
        if node.id in items:
            result.append(node)
        if not node.is_collapsed:
            for child in node.children:
                collect_visible(child, result)

    nodes: list[Node] = []
    collect_visible(drag_node, nodes)

    drag_item = items.get(drag_node.id)
    if not nodes or drag_item is None:
        return QPixmap(1, 1)

    origin_x = drag_item._pos.x
    origin_y = drag_item._pos.y

    # Relative positions: (rx, ry, width)
    rel: dict[str, tuple[float, float, float]] = {}
    for n in nodes:
        it = items.get(n.id)
        if it:
            rel[n.id] = (it._pos.x - origin_x, it._pos.y - origin_y, it._pos.width)

    if not rel:
        return QPixmap(1, 1)

    min_x = min(rx for rx, ry, w in rel.values())
    min_y = min(ry for rx, ry, w in rel.values())
    raw_w = max(rx + w for rx, ry, w in rel.values()) - min_x
    raw_h = max(ry + NODE_HEIGHT for rx, ry, w in rel.values()) - min_y

    pix_w = max(1, min(int(raw_w) + 2, _GHOST_MAX_W))
    pix_h = max(1, min(int(raw_h) + 2, _GHOST_MAX_H))

    pix = QPixmap(pix_w, pix_h)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw edges beneath nodes
    for n in nodes:
        if n.id not in rel:
            continue
        prx, pry, prw = rel[n.id]
        px1 = prx - min_x + prw
        py1 = pry - min_y + NODE_HEIGHT / 2
        for child in n.children:
            if child.id not in rel:
                continue
            crx, cry, _ = rel[child.id]
            cx1 = crx - min_x
            cy1 = cry - min_y + NODE_HEIGHT / 2
            mid = (px1 + cx1) / 2
            r   = min(5.0, abs(cy1 - py1) / 2, abs(cx1 - px1) / 2)
            path = QPainterPath()
            path.moveTo(px1, py1)
            if abs(py1 - cy1) < 1:
                path.lineTo(cx1, cy1)
            else:
                sign = 1.0 if cy1 > py1 else -1.0
                path.lineTo(mid - r, py1)
                path.quadTo(mid, py1, mid, py1 + sign * r)
                path.lineTo(mid, cy1 - sign * r)
                path.quadTo(mid, cy1, mid + r, cy1)
                path.lineTo(cx1, cy1)
            painter.setOpacity(0.25)
            painter.setPen(QPen(QColor("#888888"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    # Draw nodes with depth-based opacity fade
    for n in nodes:
        if n.id not in rel:
            continue
        rx, ry, rw = rel[n.id]
        nx = rx - min_x
        ny = ry - min_y
        if nx >= pix_w or ny >= pix_h:
            continue

        depth, curr = 0, n
        while curr is not drag_node and curr.parent is not None:
            depth += 1
            curr = curr.parent

        opacity = max(0.15, 1.0 - depth * 0.18)
        color   = _TYPE_COLORS.get(n.type, QColor("#808080"))

        painter.setOpacity(opacity)
        bg = QColor(color)
        bg.setAlpha(90)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(color, 1.5))
        painter.drawRoundedRect(QRectF(nx, ny, rw, NODE_HEIGHT), 6, 6)

        painter.setPen(QPen(Qt.GlobalColor.white if dark else QColor("#202020")))
        painter.drawText(
            QRectF(nx + 8, ny, rw - 16, NODE_HEIGHT),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            node_label(n),
        )

    painter.end()
    return pix


class GraphCanvas(QGraphicsView):
    node_selected       = Signal(str)  # node_id
    node_edit_requested = Signal(str)  # node_id
    node_exec_requested = Signal(str)  # node_id
    add_child_requested = Signal()
    delete_requested    = Signal()
    graph_changed       = Signal()     # the flow was mutated
    drop_rejected       = Signal(str)  # message for the status bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._apply_canvas_theme()
        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._apply_canvas_theme)

        self._flow:               FlowGraph | None    = None
        self._items:              dict[str, NodeItem] = {}
        self._selected_id:        str | None          = None
        self._space_held:         bool                = False
        self._pan_start:          QPoint              = QPoint()
        self._drag_candidate_id:  str | None               = None
        self._drag_start_view:    QPoint                   = QPoint()
        self._dragging:           bool                     = False
        self._drag_node_id:       str | None               = None
        self._highlight_item:     NodeItem | None          = None
        self._drag_ghost:         QGraphicsPixmapItem | None = None

        self._signals = NodeItemSignals()
        self._signals.selected.connect(self._on_node_selected)
        self._signals.edit_requested.connect(self.node_edit_requested)
        self._signals.active_toggled.connect(
            self._on_active_toggled, Qt.ConnectionType.QueuedConnection
        )
        self._signals.collapsed_toggled.connect(
            self._on_collapsed_toggled, Qt.ConnectionType.QueuedConnection
        )
        self._signals.exec_requested.connect(
            self._on_exec_requested, Qt.ConnectionType.QueuedConnection
        )

    def _apply_canvas_theme(self, *_args) -> None:
        bg = _CANVAS_BG_DARK if is_dark(QApplication.instance()) else _CANVAS_BG_LIGHT
        self.setStyleSheet(f"background: {bg};")
        self._scene.update()

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def set_flow(self, flow: FlowGraph) -> None:
        """Draw `flow` and mutate it from now on. The canvas needs the API,
        not just the graph, since every structural change it triggers goes
        through it."""
        self._flow = flow
        self._selected_id = None
        self.refresh_layout()
        # Position view so first root node appears at top-left.
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def refresh_layout(self) -> None:
        if self._flow is None:
            return
        self._scene.clear()
        self._items.clear()
        fm = QFontMetrics(QFont())
        positions = compute_layout(self._flow.graph.roots, fm.horizontalAdvance)
        self._draw(self._flow.graph.roots, positions)
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
        node = self._flow.find(node_id) if self._flow else None
        if node is None:
            return
        self._flow.set_collapsed(node_id, not node.is_collapsed)
        prev_selected = self._selected_id
        self.refresh_layout()
        if prev_selected:
            self.select_node(prev_selected)
        self.graph_changed.emit()

    def _on_active_toggled(self, node_id: str) -> None:
        node = self._flow.find(node_id) if self._flow else None
        if node is None:
            return
        self._flow.set_active(node_id, not node.is_active)
        prev_selected = self._selected_id
        self.refresh_layout()
        if prev_selected:
            self.select_node(prev_selected)
        self.graph_changed.emit()

    def _on_exec_requested(self, node_id: str) -> None:
        """Queued, like the other item-driven handlers: the receiver may open a
        modal dialog and start a process, which must not happen while the
        item's own mouse event is still on the stack."""
        self.node_exec_requested.emit(node_id)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            view_pos = event.position().toPoint()
            self._arm_drag_candidate(self.mapToScene(view_pos), view_pos)
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
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_candidate_id:
            delta = event.position().toPoint() - self._drag_start_view
            dist  = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            if not self._dragging and dist > 8:
                self._dragging     = True
                self._drag_node_id = self._drag_candidate_id
                self.setCursor(Qt.CursorShape.DragMoveCursor)
                # Create the drag ghost.
                drag_node = self._flow.find(self._drag_node_id) if self._flow else None
                if drag_node is not None:
                    pix = _create_drag_pixmap_from_layout(
                        drag_node, self._items, is_dark(QApplication.instance())
                    )
                    self._drag_ghost = QGraphicsPixmapItem(pix)
                    self._drag_ghost.setOpacity(0.82)
                    self._drag_ghost.setZValue(1000)
                    self._drag_ghost.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    self._scene.addItem(self._drag_ghost)
            if self._dragging:
                sp = self.mapToScene(event.position().toPoint())
                if self._drag_ghost:
                    self._drag_ghost.setPos(
                        sp.x() + _DRAG_GHOST_OFFSET, sp.y() + _DRAG_GHOST_OFFSET
                    )
                self._update_drop_highlight(sp)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.unsetCursor()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                sp = self.mapToScene(event.position().toPoint())
                self._perform_drop(sp)
                self._clear_drag()
                event.accept()
                return
            self._drag_candidate_id = None
        super().mouseReleaseEvent(event)

    # ── Drag-to-reparent ────────────────────────────────────────────────────

    def _arm_drag_candidate(self, scene_pos: QPointF, view_pos: QPoint) -> None:
        """Remember the node a left press could start dragging. A press on one
        of the node's buttons must not arm a reparent drag, so the decision
        goes through NodeItem.zone_at()."""
        item = self._item_at(scene_pos)
        if item is None:
            return
        if item.zone_at(item.mapFromScene(scene_pos).x()) == NodeZone.BODY:
            self._drag_candidate_id = item.node_id
            self._drag_start_view   = view_pos

    def _item_at(self, scene_pos: QPointF) -> NodeItem | None:
        for item in self._scene.items(scene_pos):
            if isinstance(item, NodeItem):
                return item
        return None

    def _update_drop_highlight(self, scene_pos: QPointF) -> None:
        candidate = self._item_at(scene_pos)
        if candidate and candidate.node_id == self._drag_node_id:
            candidate = None
        if self._highlight_item is not candidate:
            if self._highlight_item:
                self._highlight_item.set_drop_highlight(False)
            self._highlight_item = candidate
            if self._highlight_item:
                self._highlight_item.set_drop_highlight(True)

    def _perform_drop(self, scene_pos: QPointF) -> None:
        if self._drag_node_id is None or self._flow is None:
            return
        drag_node = self._flow.find(self._drag_node_id)
        if drag_node is None:
            return

        target_item = self._item_at(scene_pos)
        target_node = self._flow.find(target_item.node_id) if target_item else None

        if target_node is drag_node:
            return

        try:
            self._flow.reparent(drag_node.id, target_node.id if target_node else None)
        except GraphRuleError as error:
            self.drop_rejected.emit(rule_message(error))
            return

        # Nullify before refresh_layout() — it destroys all scene items.
        self._highlight_item = None
        self._drag_ghost     = None

        self.refresh_layout()
        self.select_node(drag_node.id)
        self.graph_changed.emit()

    def _clear_drag(self) -> None:
        if self._drag_ghost:
            self._scene.removeItem(self._drag_ghost)
            self._drag_ghost = None
        if self._highlight_item:
            self._highlight_item.set_drop_highlight(False)
            self._highlight_item = None
        self._dragging          = False
        self._drag_node_id      = None
        self._drag_candidate_id = None
        self.unsetCursor()

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
        if self._flow is None or self._selected_id is None:
            return
        node = self._flow.find(self._selected_id)
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

    def _select_sibling(self, node: Node, delta: int) -> None:
        siblings = node.parent.children if node.parent else self._flow.graph.roots
        idx = next((i for i, n in enumerate(siblings) if n.id == node.id), None)
        if idx is not None and 0 <= idx + delta < len(siblings):
            self.select_node(siblings[idx + delta].id)

    def _reorder_sibling(self, node: Node, delta: int) -> None:
        if self._flow is None:
            return
        self._flow.reorder(node.id, delta)
        self.refresh_layout()
        self.select_node(node.id)
        self.graph_changed.emit()
