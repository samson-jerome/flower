import uuid
from flower.engine.dot import to_dot, to_dot_active, write_dot, write_dot_active
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType


def _node(name, ntype=NodeType.NOOP):
    return Node(id=str(uuid.uuid4()), name=name, type=ntype)


def _link(parent, child):
    parent.children.append(child)
    child.parent = parent
    return child


def _graph():
    """setup ─ check ─┬─ deploy
                      └─ cleanup"""
    setup   = _node("setup", NodeType.SCRIPT)
    check   = _link(setup, _node("check", NodeType.IF))
    deploy  = _link(check, _node("deploy"))
    cleanup = _link(check, _node("cleanup"))
    return Graph(roots=[setup]), setup, check, deploy, cleanup


def test_to_dot_lists_every_node_and_edge():
    graph, *_ = _graph()

    assert to_dot(graph) == (
        "digraph flow {\n"
        '  n1 [label="setup"];\n'
        '  n2 [label="check"];\n'
        '  n3 [label="deploy"];\n'
        '  n4 [label="cleanup"];\n'
        "  n1 -> n2;\n"
        "  n2 -> n3;\n"
        "  n2 -> n4;\n"
        "}\n"
    )


def test_to_dot_handles_several_roots():
    first  = _node("first")
    second = _node("second")

    text = to_dot(Graph(roots=[first, second]))

    assert 'n1 [label="first"];' in text
    assert 'n2 [label="second"];' in text
    assert "->" not in text


def test_to_dot_is_deterministic_across_calls():
    graph, *_ = _graph()
    assert to_dot(graph) == to_dot(graph)


def test_to_dot_does_not_use_model_ids():
    # Node ids are regenerated on every read of a .flow, so a .dot built on
    # them would differ on each export of an unchanged file.
    graph, setup, *_ = _graph()
    assert setup.id not in to_dot(graph)


def test_to_dot_escapes_quotes_and_backslashes():
    graph = Graph(roots=[_node('say "hi"\\now')])

    assert '[label="say \\"hi\\"\\\\now"]' in to_dot(graph)


def test_to_dot_keeps_inactive_nodes():
    graph, setup, check, deploy, cleanup = _graph()
    check.is_active = False

    text = to_dot(graph)

    assert 'label="check"' in text
    assert 'label="deploy"' in text


def test_to_dot_carries_no_state_attribute():
    graph, setup, check, deploy, cleanup = _graph()
    check.is_active     = False
    setup.is_executable = True

    text = to_dot(graph)

    for attribute in ("style", "color", "fillcolor", "shape", "rankdir", "penwidth"):
        assert attribute not in text


def test_to_dot_active_drops_an_inactive_node_and_its_subtree():
    graph, setup, check, deploy, cleanup = _graph()
    check.is_active = False

    text = to_dot_active(graph)

    assert 'label="setup"' in text
    assert "check" not in text
    assert "deploy" not in text          # the subtree goes with it
    assert "->" not in text              # setup's only child is gone


def test_to_dot_active_renumbers_the_remaining_nodes():
    graph, setup, check, deploy, cleanup = _graph()
    deploy.is_active = False

    text = to_dot_active(graph)

    assert 'n3 [label="cleanup"];' in text
    assert "n4" not in text


def test_to_dot_active_equals_to_dot_when_everything_is_active():
    graph, *_ = _graph()
    assert to_dot_active(graph) == to_dot(graph)


def test_write_dot_and_write_dot_active(tmp_path):
    graph, setup, check, deploy, cleanup = _graph()
    check.is_active = False

    write_dot(graph, tmp_path / "all.dot")
    write_dot_active(graph, tmp_path / "run.dot")

    assert "check" in (tmp_path / "all.dot").read_text(encoding="utf-8")
    assert "check" not in (tmp_path / "run.dot").read_text(encoding="utf-8")
