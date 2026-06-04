from __future__ import annotations
from dataclasses import dataclass, field
from flower.models.node import Node, Variable


@dataclass
class Graph:
    roots:      list[Node]     = field(default_factory=list)
    variables:  list[Variable] = field(default_factory=list)
    created_at: str            = ""
    updated_at: str            = ""
