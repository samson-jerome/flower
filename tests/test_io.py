import uuid
from pathlib import Path
from flower.models.node import Node, NodeType, Variable
from flower.models.graph import Graph
from flower.io.xml_writer import graph_to_xml, write_flow


def _make_graph():
    script = Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": "make build && make test"},
        variables=[Variable(name="TARGET", value="release")],
    )
    if_node = Node(
        id=str(uuid.uuid4()), name="check", type=NodeType.IF,
        type_data={"condition": "exit_code == 0"},
    )
    script.children.append(if_node)
    if_node.parent = script
    return Graph(
        roots=[script],
        variables=[Variable(name="ENV", value="prod", description="env")],
        created_at="2026-06-04",
        updated_at="2026-06-04",
    )


def test_xml_output_is_bytes():
    xml = graph_to_xml(_make_graph())
    assert isinstance(xml, bytes)
    assert b"<?xml" in xml


def test_xml_contains_node_name():
    assert b"build" in graph_to_xml(_make_graph())


def test_xml_cdata_body():
    assert b"<![CDATA[make build" in graph_to_xml(_make_graph())


def test_xml_global_var():
    assert b'name="ENV"' in graph_to_xml(_make_graph())


def test_write_flow_creates_file(tmp_path):
    path = tmp_path / "out.flow"
    write_flow(_make_graph(), path)
    assert path.exists()
    assert path.stat().st_size > 0
