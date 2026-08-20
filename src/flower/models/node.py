from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum


class NodeType(StrEnum):
    NOOP   = "noop"
    SCRIPT = "script"
    DATA   = "data"
    IF     = "if"
    LOOP   = "loop"


MAX_CHILDREN: dict[NodeType, int] = {
    NodeType.IF: 2,
}


class VariableOperation(StrEnum):
    ASSIGN = "assign"
    CONCAT = "concat"
    ADD    = "add"


@dataclass
class Variable:
    name:        str
    value:       str
    description: str  = ""
    active:      bool = True
    operation:   str  = VariableOperation.ASSIGN


@dataclass
class Node:
    id:            str
    name:          str
    type:          NodeType
    is_active:     bool           = True
    is_collapsed:  bool           = False
    is_executable: bool           = False
    description:   str            = ""
    notes:         str            = ""
    variables:     list[Variable] = field(default_factory=list)
    type_data:     dict           = field(default_factory=dict)
    children:      list[Node]     = field(default_factory=list)
    parent:        Node | None    = field(default=None, repr=False)


EXECUTABLE_TYPES: frozenset[NodeType] = frozenset({NodeType.SCRIPT, NodeType.DATA})


def can_exec(node: Node) -> bool:
    """Whether the node's Exec affordances (canvas pill, editor button) apply:
    the user marked it executable and its type supports partial execution.
    The type check also neutralizes a hand-edited .flow that marks a
    noop/if/loop node executable. Being clickable additionally requires
    node.is_active -- deliberately not folded in here, since the pill stays
    visible (greyed) on an inactive node."""
    return node.is_executable and node.type in EXECUTABLE_TYPES
