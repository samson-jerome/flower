import uuid
import re
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


from flower.io.xml_reader import read_flow


def test_roundtrip_roots_count(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    assert len(read_flow(path).roots) == 1


def test_roundtrip_node_name(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    assert read_flow(path).roots[0].name == "build"


def test_roundtrip_script_body(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    assert read_flow(path).roots[0].type_data["body"] == "make build && make test"


def test_roundtrip_global_var(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    loaded = read_flow(path)
    assert loaded.variables[0].name == "ENV"
    assert loaded.variables[0].value == "prod"


def test_roundtrip_child_node(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    child = read_flow(path).roots[0].children[0]
    assert child.name == "check"
    assert child.type == NodeType.IF
    assert child.type_data["condition"] == "exit_code == 0"


def test_roundtrip_child_parent_ref(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    loaded = read_flow(path)
    assert loaded.roots[0].children[0].parent is loaded.roots[0]


def test_roundtrip_local_var(tmp_path):
    path = tmp_path / "test.flow"
    write_flow(_make_graph(), path)
    assert read_flow(path).roots[0].variables[0].name == "TARGET"


def test_roundtrip_loop(tmp_path):
    loop = Node(
        id=str(uuid.uuid4()), name="iter", type=NodeType.LOOP,
        type_data={"index": "i", "mode": "range", "start": 1, "end": 5, "step": 1, "items": ""},
    )
    path = tmp_path / "loop.flow"
    write_flow(Graph(roots=[loop]), path)
    d = read_flow(path).roots[0].type_data
    assert d["index"] == "i"
    assert d["start"] == 1
    assert d["end"] == 5


def test_roundtrip_loop_expression(tmp_path):
    # The expression is CDATA-wrapped: it may hold <, &, quotes and newlines.
    expression = "ls <dir> & grep \"l'été\"\n  | sort"
    loop = Node(
        id=str(uuid.uuid4()), name="iter", type=NodeType.LOOP,
        type_data={
            "index": "f", "mode": "expression", "start": 0, "end": 0, "step": 1,
            "items": "", "expression": expression,
        },
    )
    path = tmp_path / "loop_expr.flow"
    write_flow(Graph(roots=[loop]), path)
    d = read_flow(path).roots[0].type_data
    assert d["mode"] == "expression"
    assert d["expression"] == expression


def test_read_loop_without_expression_element_defaults_to_empty(tmp_path):
    # Backward compatibility with .flow files written before this mode existed.
    loop = Node(
        id=str(uuid.uuid4()), name="iter", type=NodeType.LOOP,
        type_data={
            "index": "i", "mode": "range", "start": 0, "end": 2, "step": 1,
            "items": "", "expression": "ls",
        },
    )
    path = tmp_path / "legacy.flow"
    write_flow(Graph(roots=[loop]), path)
    stripped = re.sub(
        r"<expression>.*?</expression>", "", path.read_text(encoding="utf-8"), flags=re.DOTALL,
    )
    assert "<expression>" not in stripped, "the element was not stripped; test is void"
    path.write_text(stripped, encoding="utf-8")
    assert read_flow(path).roots[0].type_data["expression"] == ""


def test_roundtrip_graph_notes(tmp_path):
    g = _make_graph()
    g.notes = "Global notes <with> & special chars\nmultiline"
    path = tmp_path / "notes.flow"
    write_flow(g, path)
    assert read_flow(path).notes == "Global notes <with> & special chars\nmultiline"


def test_roundtrip_node_notes(tmp_path):
    g = _make_graph()
    g.roots[0].notes = "Build step notes\nline 2"
    path = tmp_path / "node-notes.flow"
    write_flow(g, path)
    assert read_flow(path).roots[0].notes == "Build step notes\nline 2"


def test_missing_notes_defaults_to_empty(tmp_path):
    # Backward compat: a .flow without <notes> elements still loads
    path = tmp_path / "no-notes.flow"
    write_flow(_make_graph(), path)
    loaded = read_flow(path)
    assert loaded.notes == ""
    assert loaded.roots[0].notes == ""
