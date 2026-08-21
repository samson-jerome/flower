import uuid
import pytest
from flower.engine.api import FlowGraph
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType


def _node(name, ntype=NodeType.NOOP):
    return Node(id=str(uuid.uuid4()), name=name, type=ntype)


def _tree():
    """root ─ child ─ grandchild, plus a second root."""
    root, child, grandchild, other = (
        _node("root"), _node("child"), _node("grandchild"), _node("other")
    )
    root.children.append(child)
    child.parent = root
    child.children.append(grandchild)
    grandchild.parent = child
    return FlowGraph(Graph(roots=[root, other])), root, child, grandchild, other


def test_new_starts_on_an_empty_clean_graph():
    flow = FlowGraph.new()
    assert flow.graph.roots == []
    assert flow.path is None
    assert flow.is_dirty is False


def test_open_reads_the_file_and_starts_clean(tmp_path):
    source = FlowGraph(Graph(roots=[_node("root")]))
    path = tmp_path / "demo.flow"
    source.save(path)

    flow = FlowGraph.open(path)

    assert [n.name for n in flow.graph.roots] == ["root"]
    assert flow.path == path
    assert flow.is_dirty is False


def test_save_stamps_updated_at_and_clears_dirty(tmp_path):
    flow = FlowGraph(Graph(roots=[_node("root")]))
    flow.mark_modified()

    flow.save(tmp_path / "demo.flow")

    assert flow.is_dirty is False
    assert flow.graph.updated_at != ""
    assert (tmp_path / "demo.flow").exists()


def test_save_without_a_path_raises():
    with pytest.raises(ValueError):
        FlowGraph.new().save()


def test_save_remembers_the_path_it_was_given(tmp_path):
    flow = FlowGraph.new()
    path = tmp_path / "demo.flow"

    flow.save(path)
    flow.save()

    assert flow.path == path


def test_find_walks_the_whole_tree():
    flow, root, child, grandchild, _ = _tree()
    assert flow.find(grandchild.id) is grandchild
    assert flow.find("absent") is None


def test_methods_taking_an_unknown_id_raise_value_error():
    flow, *_ = _tree()
    with pytest.raises(ValueError):
        flow._require("absent")


def test_unique_name_suffixes_only_on_collision():
    flow, root, child, *_ = _tree()
    assert flow.unique_name("libre") == "libre"
    assert flow.unique_name("root") == "root_1"


def test_unique_name_skips_taken_suffixes():
    root = _node("dup")
    taken = _node("dup_1")
    root.children.append(taken)
    taken.parent = root
    flow = FlowGraph(Graph(roots=[root]))

    assert flow.unique_name("dup") == "dup_2"
