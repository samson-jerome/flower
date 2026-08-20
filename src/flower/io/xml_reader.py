from __future__ import annotations
import uuid
from pathlib import Path
from lxml import etree
from flower.models.node import Node, NodeType, Variable, VariableOperation
from flower.models.graph import Graph


def _read_vars(el) -> list[Variable]:
    vars_el = el.find("vars")
    if vars_el is None:
        return []
    return [
        Variable(
            name=v.get("name", ""),
            value=v.get("value", ""),
            description=v.get("description", ""),
            active=v.get("active", "1") == "1",
            operation=v.get("operation", VariableOperation.ASSIGN),
        )
        for v in vars_el.findall("var")
    ]


def _read_node(el, parent: Node | None = None) -> Node:
    ntype = NodeType(el.get("type", "noop"))
    node = Node(
        id=str(uuid.uuid4()),
        name=el.get("name", ""),
        type=ntype,
        is_active=el.get("active", "1") == "1",
        is_collapsed=el.get("collapsed", "0") == "1",
        is_executable=el.get("executable", "0") == "1",
        description=el.findtext("description", "") or "",
        notes=el.findtext("notes", "") or "",
        variables=_read_vars(el),
        parent=parent,
    )

    d: dict = {}
    if ntype == NodeType.SCRIPT:
        d = {"language": el.findtext("language", "") or "", "body": el.findtext("body", "") or ""}
    elif ntype == NodeType.DATA:
        d = {"command": el.findtext("command", "") or "", "content": el.findtext("body", "") or ""}
    elif ntype == NodeType.IF:
        d = {"condition": el.findtext("condition", "") or ""}
    elif ntype == NodeType.LOOP:
        d = {
            "index": el.findtext("index", "") or "",
            "mode":  el.findtext("mode", "range") or "range",
            "start": int(el.findtext("start", "0") or 0),
            "end":   int(el.findtext("end", "0") or 0),
            "step":  int(el.findtext("step", "1") or 1),
            "items": el.findtext("items", "") or "",
            "expression": el.findtext("expression", "") or "",
        }
    node.type_data = d

    children_el = el.find("children")
    if children_el is not None:
        for child_el in children_el.findall("node"):
            node.children.append(_read_node(child_el, parent=node))

    return node


def read_flow(path: Path) -> Graph:
    tree = etree.parse(str(path))
    root = tree.getroot()

    info = root.find("info")
    created_at = info.findtext("created_at", "") if info is not None else ""
    updated_at = info.findtext("updated_at", "") if info is not None else ""
    notes      = info.findtext("notes", "")      if info is not None else ""

    children_el = root.find("children")
    roots = [_read_node(el) for el in children_el.findall("node")] if children_el is not None else []

    return Graph(
        roots=roots,
        variables=_read_vars(root),
        notes=notes or "",
        created_at=created_at or "",
        updated_at=updated_at or "",
    )
