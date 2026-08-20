from __future__ import annotations
from pathlib import Path
from lxml import etree
from flower.models.node import Node, NodeType, Variable
from flower.models.graph import Graph


def _var_el(parent, v: Variable) -> None:
    etree.SubElement(parent, "var",
        name=v.name, value=v.value, description=v.description,
        active="1" if v.active else "0", operation=v.operation,
    )


def _node_to_xml(node: Node, parent_el) -> None:
    node_el = etree.SubElement(parent_el, "node",
        type=node.type, name=node.name,
        active="1" if node.is_active else "0",
        collapsed="1" if node.is_collapsed else "0",
        executable="1" if node.is_executable else "0",
    )
    etree.SubElement(node_el, "description").text = node.description
    etree.SubElement(node_el, "notes").text = etree.CDATA(node.notes or "")

    vars_el = etree.SubElement(node_el, "vars")
    for v in node.variables:
        _var_el(vars_el, v)

    d = node.type_data
    if node.type == NodeType.SCRIPT:
        etree.SubElement(node_el, "language").text = d.get("language", "")
        etree.SubElement(node_el, "body").text = etree.CDATA(d.get("body", ""))
    elif node.type == NodeType.DATA:
        etree.SubElement(node_el, "command").text = d.get("command", "")
        etree.SubElement(node_el, "body").text = etree.CDATA(d.get("content", ""))
    elif node.type == NodeType.IF:
        etree.SubElement(node_el, "condition").text = d.get("condition", "")
    elif node.type == NodeType.LOOP:
        for key in ("index", "mode"):
            etree.SubElement(node_el, key).text = str(d.get(key, ""))
        for key in ("start", "end", "step"):
            etree.SubElement(node_el, key).text = str(d.get(key, 0))
        etree.SubElement(node_el, "items").text = etree.CDATA(d.get("items", ""))
        etree.SubElement(node_el, "expression").text = etree.CDATA(d.get("expression", ""))

    children_el = etree.SubElement(node_el, "children")
    for child in node.children:
        _node_to_xml(child, children_el)


def graph_to_xml(graph: Graph) -> bytes:
    root = etree.Element("flow", version="1.0")

    info = etree.SubElement(root, "info")
    etree.SubElement(info, "created_at").text = graph.created_at
    etree.SubElement(info, "updated_at").text = graph.updated_at
    etree.SubElement(info, "notes").text = etree.CDATA(graph.notes or "")

    vars_el = etree.SubElement(root, "vars")
    for v in graph.variables:
        _var_el(vars_el, v)

    children_el = etree.SubElement(root, "children")
    for node in graph.roots:
        _node_to_xml(node, children_el)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def write_flow(graph: Graph, path: Path) -> None:
    path.write_bytes(graph_to_xml(graph))
