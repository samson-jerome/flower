from __future__ import annotations
from flower.engine.models.node import NodeType


class GraphRuleError(Exception):
    """A mutation refused because it would break a model rule.

    Carries structured data, never a user-facing sentence: the wording
    belongs to the presentation layer (see flower.app.messages)."""


class MaxChildrenError(GraphRuleError):
    def __init__(self, node_type: NodeType, max_children: int):
        super().__init__(f"a {node_type} node accepts at most {max_children} children")
        self.node_type    = node_type
        self.max_children = max_children


class CycleError(GraphRuleError):
    def __init__(self, node_id: str):
        super().__init__(f"node {node_id!r} cannot become its own descendant")
        self.node_id = node_id
