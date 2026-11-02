"""Opening a node in the form and applying it untouched must not change the
.flow output: the editor widgets are a view over type_data, never a filter."""
import uuid
from flower.engine.io.xml_writer import graph_to_xml
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType, Variable
from flower.app.editor.node_form import NodeForm


_LOOP_DATA = {
    "index": "i", "start": -5, "end": 9999, "step": 3,
    "items": "a\nb", "expression": "ls",
}


def _node(name, ntype, type_data, **kwargs):
    return Node(
        id=str(uuid.uuid4()), name=name, type=ntype, type_data=type_data,
        description=f"{name}\nsecond line",
        variables=[Variable(name=f"V_{name}", value="1")],
        **kwargs,
    )


def _sample_graph() -> Graph:
    root = _node("root", NodeType.NOOP, {})
    children = [
        _node("script", NodeType.SCRIPT,
              {"language": "python",
               "body": "def f():\n\tif x:\n        return 'é'\n  \n"},
              is_executable=True),
        _node("data", NodeType.DATA,
              {"command": "cat > out.json", "content": '{"a": [1, 2]}\n'},
              is_active=False),
        _node("if", NodeType.IF, {"condition": '[ -f "$F" ]'}),
    ] + [
        _node(f"loop_{mode}", NodeType.LOOP, {**_LOOP_DATA, "mode": mode})
        for mode in ("range", "list", "expression")
    ]
    for child in children:
        child.parent = root
        root.children.append(child)
    return Graph(roots=[root])


def _all_nodes(graph: Graph):
    stack = list(graph.roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)


def test_opening_and_applying_every_node_leaves_the_xml_unchanged(qapp):
    graph = _sample_graph()
    before = graph_to_xml(graph)
    for node in _all_nodes(graph):
        NodeForm(node).apply_to_node()
    assert graph_to_xml(graph) == before


def test_get_node_data_returns_type_data_equal_to_the_node(qapp):
    for node in _all_nodes(_sample_graph()):
        assert NodeForm(node).get_node_data()["type_data"] == node.type_data
