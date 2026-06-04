from __future__ import annotations
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsSimpleTextItem
from PySide6.QtGui import QPen, QColor, QBrush
from PySide6.QtCore import Qt, QPointF
from flower.models.node import NodeType
from flower.layout.tree_layout import NodePos
from flower.ui.node_item import NODE_HEIGHT

_EDGE_COLOR  = QColor("#888888")
_COLOR_TRUE  = QColor("#55dd55")
_COLOR_FALSE = QColor("#dd5555")


class EdgeItem(QGraphicsLineItem):
    """Line from parent right edge to child left edge. For `if` nodes, adds true/false labels on the first two branches."""

    def __init__(self, parent_pos: NodePos, child_pos: NodePos,
                 child_index: int, parent_type: NodeType):
        px = parent_pos.x + parent_pos.width
        py = parent_pos.y + NODE_HEIGHT / 2
        cx = child_pos.x
        cy = child_pos.y + NODE_HEIGHT / 2
        super().__init__(px, py, cx, cy)
        self.setPen(QPen(_EDGE_COLOR, 1.2, Qt.PenStyle.SolidLine))

        if parent_type == NodeType.IF and child_index < 2:
            label_text  = "true" if child_index == 0 else "false"
            label_color = _COLOR_TRUE if child_index == 0 else _COLOR_FALSE
            label = QGraphicsSimpleTextItem(label_text, self)
            label.setPos(QPointF((px + cx) / 2 - 10, (py + cy) / 2 - 10))
            label.setBrush(QBrush(label_color))
