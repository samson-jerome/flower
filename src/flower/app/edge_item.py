from __future__ import annotations
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsSimpleTextItem
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath
from PySide6.QtCore import Qt, QPointF
from flower.engine.models.node import NodeType
from flower.app.layout.tree_layout import NodePos
from flower.app.node_item import NODE_HEIGHT

_EDGE_COLOR  = QColor("#888888")
_COLOR_TRUE  = QColor("#55dd55")
_COLOR_FALSE = QColor("#dd5555")
_CORNER_R    = 6.0


class EdgeItem(QGraphicsPathItem):
    """Orthogonal connector parent → child with softly rounded corners."""

    def __init__(self, parent_pos: NodePos, child_pos: NodePos,
                 child_index: int, parent_type: NodeType):
        px = parent_pos.x + parent_pos.width
        py = parent_pos.y + NODE_HEIGHT / 2
        cx = child_pos.x
        cy = child_pos.y + NODE_HEIGHT / 2
        mid_x = (px + cx) / 2

        path = QPainterPath()
        path.moveTo(px, py)

        if abs(py - cy) < 1.0:
            # Same row: straight horizontal line.
            path.lineTo(cx, cy)
        else:
            r = min(_CORNER_R, abs(cy - py) / 2, (cx - px) / 2)
            sign = 1.0 if cy > py else -1.0
            # Horizontal → vertical corner.
            path.lineTo(mid_x - r, py)
            path.quadTo(mid_x, py, mid_x, py + sign * r)
            # Vertical → horizontal corner.
            path.lineTo(mid_x, cy - sign * r)
            path.quadTo(mid_x, cy, mid_x + r, cy)
            path.lineTo(cx, cy)

        super().__init__(path)
        self.setPen(QPen(_EDGE_COLOR, 1.2, Qt.PenStyle.SolidLine))
        self.setBrush(Qt.BrushStyle.NoBrush)

        if parent_type == NodeType.IF and child_index < 2:
            label_text  = "true" if child_index == 0 else "false"
            label_color = _COLOR_TRUE if child_index == 0 else _COLOR_FALSE
            label = QGraphicsSimpleTextItem(label_text, self)
            label.setPos(QPointF(mid_x + 2, (py + cy) / 2 - 8))
            label.setBrush(QBrush(label_color))
