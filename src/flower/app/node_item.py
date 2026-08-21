from __future__ import annotations
from enum import StrEnum
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt, QRectF, Signal, QObject
from flower.engine.models.node import Node, NodeType, can_exec
from flower.app.layout.tree_layout import NodePos, node_label, EXEC_BTN_W, EXEC_ZONE_W
from flower.app.theme import is_dark

NODE_HEIGHT     = 32.0
ACTIVE_ZONE_W   = 20.0   # activity dot on the left
COLLAPSE_ZONE_W = 28.0   # −/+ button plus its right margin
RIGHT_PAD       = 8.0    # right margin when there is no −/+ button
EXEC_BTN_H      = 18.0


class NodeZone(StrEnum):
    """The interactive zones of a node, left to right. Naming them keeps the
    geometry in one place: it used to be recomputed from bare numbers in four
    methods here and one in GraphCanvas."""
    ACTIVE   = "active"
    EXEC     = "exec"
    COLLAPSE = "collapse"
    BODY     = "body"

_TYPE_COLORS: dict[NodeType, QColor] = {
    NodeType.NOOP:   QColor("#808080"),
    NodeType.SCRIPT: QColor("#4a90d9"),
    NodeType.DATA:   QColor("#5aaa5a"),
    NodeType.IF:     QColor("#d9a040"),
    NodeType.LOOP:   QColor("#9b59b6"),
}


class NodeItemSignals(QObject):
    selected          = Signal(str)  # node_id
    edit_requested    = Signal(str)  # node_id
    active_toggled    = Signal(str)  # node_id
    collapsed_toggled = Signal(str)  # node_id
    exec_requested    = Signal(str)  # node_id


class NodeItem(QGraphicsItem):
    def __init__(self, node: Node, pos: NodePos, signals: NodeItemSignals):
        super().__init__()
        self._node           = node
        self._pos            = pos
        self._signals        = signals
        self._selected       = False
        self._drop_highlight = False
        self.setPos(pos.x, pos.y)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def node_id(self) -> str:
        return self._node.id

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._pos.width, NODE_HEIGHT)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_drop_highlight(self, active: bool) -> None:
        self._drop_highlight = active
        self.update()

    def refresh(self, node: Node, pos: NodePos) -> None:
        self._node = node
        self._pos  = pos
        self.setPos(pos.x, pos.y)
        self.prepareGeometryChange()
        self.update()

    def _exec_rect(self) -> QRectF | None:
        """Geometry of the Exec pill, or None when the node has none. Shared by
        paint() and zone_at() so what is drawn and what is clickable cannot
        drift apart."""
        if not can_exec(self._node):
            return None
        right = self._pos.width - (COLLAPSE_ZONE_W if self._node.children else RIGHT_PAD)
        return QRectF(right - EXEC_BTN_W, (NODE_HEIGHT - EXEC_BTN_H) / 2,
                      EXEC_BTN_W, EXEC_BTN_H)

    def _label_rect(self) -> QRectF:
        """Geometry of the label text, leaving a 6px gap before whichever
        button zone (collapse and/or exec pill) is present on the right, or
        the plain right padding when neither is. Shared by paint() and the
        tests so the drawn gap and the asserted gap cannot drift apart."""
        n = len(self._node.children)
        btn_w = COLLAPSE_ZONE_W if n > 0 else RIGHT_PAD
        if self._exec_rect() is not None:
            btn_w += EXEC_ZONE_W
        return QRectF(ACTIVE_ZONE_W, 0, self._pos.width - ACTIVE_ZONE_W - btn_w, NODE_HEIGHT)

    def zone_at(self, x: float) -> NodeZone:
        """Which interactive zone the node-local x falls into. Single source of
        truth for this item's own mouse handling and for GraphCanvas's
        drag-candidate test, which must not arm a reparent drag on a button."""
        if x < ACTIVE_ZONE_W:
            return NodeZone.ACTIVE
        if self._node.children and x > self._pos.width - COLLAPSE_ZONE_W:
            return NodeZone.COLLAPSE
        rect = self._exec_rect()
        if rect is not None and rect.left() <= x <= rect.right():
            return NodeZone.EXEC
        return NodeZone.BODY

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        dark  = is_dark(QApplication.instance())
        # Low-alpha node fills let the canvas show through, so the accent
        # (label, selection border, button overlay) must flip with the
        # canvas theme to stay readable — pure white on a light canvas
        # would be invisible.
        accent = Qt.GlobalColor.white if dark else QColor("#202020")
        overlay_rgb = (255, 255, 255) if dark else (0, 0, 0)

        color  = _TYPE_COLORS.get(self._node.type, QColor("#808080"))
        rect   = self.boundingRect()
        radius = 6.0

        bg = QColor(color)
        bg.setAlpha(60 if self._node.is_active else 30)
        painter.setBrush(QBrush(bg))
        border_pen = QPen(accent if self._selected else color, 2)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, radius, radius)

        if self._selected:
            outline = QPen(color, 1)
            painter.setPen(outline)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), radius + 2, radius + 2)

        dot_color = QColor("#55ff55") if self._node.is_active else QColor("#888888")
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, int(rect.height() / 2) - 4, 8, 8)

        if not self._node.is_active:
            painter.setOpacity(0.5)

        n = len(self._node.children)
        exec_rect = self._exec_rect()

        # Label
        painter.setPen(QPen(accent))
        painter.drawText(
            self._label_rect(),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            node_label(self._node),
        )

        # Exec pill -- same overlay palette as the −/+ button, stronger and
        # bold so an action reads as one. The 0.5 opacity already applied to
        # an inactive node fades it too, which is the intended "visible but
        # inert" look.
        if exec_rect is not None:
            painter.setBrush(QBrush(QColor(*overlay_rgb, 70)))
            painter.setPen(QPen(QColor(*overlay_rgb, 160), 1))
            painter.drawRoundedRect(exec_rect, 4, 4)
            saved_font = painter.font()
            pill_font  = QFont(saved_font)
            pill_font.setPointSizeF(max(7.0, saved_font.pointSizeF() - 1.5))
            pill_font.setBold(True)
            painter.setFont(pill_font)
            painter.setPen(QPen(accent))
            painter.drawText(exec_rect, Qt.AlignmentFlag.AlignCenter, "Exec")
            painter.setFont(saved_font)

        # Collapse / expand button (centré dans la zone, avec 8px de marge droite)
        if n > 0:
            btn_rect = QRectF(self._pos.width - 22.0, (NODE_HEIGHT - 14) / 2, 14, 14)
            painter.setBrush(QBrush(QColor(*overlay_rgb, 40)))
            painter.setPen(QPen(QColor(*overlay_rgb, 100), 1))
            painter.drawRoundedRect(btn_rect, 3, 3)
            painter.setPen(QPen(accent))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter,
                             "−" if not self._node.is_collapsed else "+")

        painter.setOpacity(1.0)

        # Drop-target highlight (drawn last, always opaque)
        if self._drop_highlight:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ffd700"), 2))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

    def mousePressEvent(self, event) -> None:
        zone = self.zone_at(event.pos().x())
        if zone == NodeZone.ACTIVE:
            self._signals.active_toggled.emit(self._node.id)
            event.accept()
            return
        if zone == NodeZone.COLLAPSE:
            self._signals.collapsed_toggled.emit(self._node.id)
            event.accept()
            return
        if zone == NodeZone.EXEC:
            # An inactive node is never emitted by the generator, so a partial
            # script stopping on it would hold nothing: swallow the click.
            if self._node.is_active:
                self._signals.exec_requested.emit(self._node.id)
            event.accept()
            return
        self._signals.selected.emit(self._node.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.zone_at(event.pos().x()) != NodeZone.BODY:
            event.accept()
            return
        self._signals.edit_requested.emit(self._node.id)
        super().mouseDoubleClickEvent(event)
