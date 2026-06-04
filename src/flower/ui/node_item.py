from __future__ import annotations
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt, QRectF, Signal, QObject
from flower.models.node import Node, NodeType
from flower.layout.tree_layout import NodePos, node_label

NODE_HEIGHT = 32.0

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


class NodeItem(QGraphicsItem):
    def __init__(self, node: Node, pos: NodePos, signals: NodeItemSignals):
        super().__init__()
        self._node     = node
        self._pos      = pos
        self._signals  = signals
        self._selected = False
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

    def refresh(self, node: Node, pos: NodePos) -> None:
        self._node = node
        self._pos  = pos
        self.setPos(pos.x, pos.y)
        self.prepareGeometryChange()
        self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        color  = _TYPE_COLORS.get(self._node.type, QColor("#808080"))
        rect   = self.boundingRect()
        radius = 6.0

        bg = QColor(color)
        bg.setAlpha(60 if self._node.is_active else 30)
        painter.setBrush(QBrush(bg))
        border_pen = QPen(Qt.GlobalColor.white if self._selected else color, 2)
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
        btn_w = 28.0 if n > 0 else 0.0  # zone réservée au bouton (inclut marge droite)

        # Label
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(
            QRectF(20, 0, self._pos.width - 20 - btn_w, NODE_HEIGHT),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            node_label(self._node),
        )

        # Collapse / expand button (centré dans la zone, avec 8px de marge droite)
        if n > 0:
            btn_rect = QRectF(self._pos.width - 22.0, (NODE_HEIGHT - 14) / 2, 14, 14)
            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            painter.drawRoundedRect(btn_rect, 3, 3)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter,
                             "−" if not self._node.is_collapsed else "+")

        painter.setOpacity(1.0)

    def _in_collapse_zone(self, x: float) -> bool:
        return len(self._node.children) > 0 and x > self._pos.width - 28

    def mousePressEvent(self, event) -> None:
        x = event.pos().x()
        if x < 20:
            self._signals.active_toggled.emit(self._node.id)
            event.accept()
            return
        if self._in_collapse_zone(x):
            self._signals.collapsed_toggled.emit(self._node.id)
            event.accept()
            return
        self._signals.selected.emit(self._node.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        x = event.pos().x()
        if x < 20 or self._in_collapse_zone(x):
            event.accept()
            return
        self._signals.edit_requested.emit(self._node.id)
        super().mouseDoubleClickEvent(event)
