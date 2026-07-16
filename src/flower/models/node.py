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
    id:           str
    name:         str
    type:         NodeType
    is_active:    bool           = True
    is_collapsed: bool           = False
    description:  str            = ""
    notes:        str            = ""
    variables:    list[Variable] = field(default_factory=list)
    type_data:    dict           = field(default_factory=dict)
    children:     list[Node]     = field(default_factory=list)
    parent:       Node | None    = field(default=None, repr=False)
