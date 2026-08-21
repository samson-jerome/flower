import uuid
import pytest
from flower.engine.api import FlowGraph
from flower.engine.errors import CycleError, MaxChildrenError
from flower.engine.execution.runner import DEFAULT_TERMINAL
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


def _script_flow(tmp_path):
    """A two-node flow saved to disk, ready to generate a script from."""
    first  = _node("first",  NodeType.SCRIPT)
    second = _node("second", NodeType.SCRIPT)
    first.type_data  = {"language": "", "body": "echo un"}
    second.type_data = {"language": "", "body": "echo deux"}
    first.children.append(second)
    second.parent = first
    flow = FlowGraph(Graph(roots=[first]))
    flow.save(tmp_path / "demo.flow")
    return flow, first, second


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


def test_save_leaves_the_flow_unchanged_when_the_write_fails(tmp_path):
    flow = FlowGraph(Graph(roots=[_node("root")]))
    flow.mark_modified()
    previous_updated_at = flow.graph.updated_at
    previous_path = flow.path
    bad_path = tmp_path / "absent" / "demo.flow"

    with pytest.raises(OSError):
        flow.save(bad_path)

    assert flow.graph.updated_at == previous_updated_at
    assert flow.path == previous_path
    assert flow.is_dirty is True

    good_path = tmp_path / "demo.flow"
    flow.save(good_path)

    assert flow.path == good_path
    assert flow.is_dirty is False


def test_save_leaves_the_flow_unchanged_when_serialization_fails(tmp_path):
    flow = FlowGraph(Graph(notes="avant\x0capres"))
    flow.mark_modified()
    previous_updated_at = flow.graph.updated_at
    previous_path = flow.path
    target = tmp_path / "demo.flow"

    with pytest.raises(ValueError):
        flow.save(target)

    assert flow.graph.updated_at == previous_updated_at
    assert flow.path == previous_path
    assert flow.is_dirty is True
    assert not target.exists()


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


def test_add_node_appends_to_the_parent_and_marks_dirty():
    flow, root, child, *_ = _tree()

    added = flow.add_node(root.id, NodeType.SCRIPT)

    assert added in root.children
    assert added.parent is root
    assert added.type == NodeType.SCRIPT
    assert flow.is_dirty is True


def test_add_node_without_a_parent_creates_a_root():
    flow, root, *_ = _tree()

    added = flow.add_node(None)

    assert added in flow.graph.roots
    assert added.parent is None


def test_add_node_names_it_uniquely():
    flow, root, *_ = _tree()

    first  = flow.add_node(root.id, name="task")
    second = flow.add_node(root.id, name="task")

    assert first.name == "task"
    assert second.name == "task_1"


def test_add_node_gives_each_node_its_own_id():
    flow, root, *_ = _tree()
    ids = {flow.add_node(root.id).id for _ in range(3)}
    assert len(ids) == 3


def test_add_node_refuses_a_third_child_on_an_if_node():
    parent = _node("check", NodeType.IF)
    flow = FlowGraph(Graph(roots=[parent]))
    flow.add_node(parent.id)
    flow.add_node(parent.id)

    with pytest.raises(MaxChildrenError) as excinfo:
        flow.add_node(parent.id)

    assert excinfo.value.max_children == 2
    assert excinfo.value.node_type == NodeType.IF
    assert len(parent.children) == 2


def test_remove_node_detaches_it_from_its_parent():
    flow, root, child, *_ = _tree()

    flow.remove_node(child.id)

    assert child not in root.children
    assert flow.is_dirty is True


def test_remove_node_detaches_a_root():
    flow, root, *_ = _tree()

    flow.remove_node(root.id)

    assert root not in flow.graph.roots


def test_reparent_moves_the_node_and_its_subtree():
    flow, root, child, grandchild, other = _tree()

    flow.reparent(child.id, other.id)

    assert child not in root.children
    assert child in other.children
    assert child.parent is other
    assert grandchild.parent is child          # the subtree follows
    assert flow.is_dirty is True


def test_reparent_to_none_makes_it_a_root():
    flow, root, child, *_ = _tree()

    flow.reparent(child.id, None)

    assert child in flow.graph.roots
    assert child.parent is None
    assert child not in root.children


def test_reparent_appends_last_by_default_and_honours_an_index():
    flow, root, child, grandchild, other = _tree()
    first = flow.add_node(other.id, name="first")

    flow.reparent(child.id, other.id)
    assert other.children == [first, child]

    flow.reparent(child.id, other.id, index=0)
    assert other.children == [child, first]


def test_reparent_onto_itself_raises():
    flow, root, child, *_ = _tree()
    with pytest.raises(CycleError):
        flow.reparent(child.id, child.id)


def test_reparent_onto_its_own_descendant_raises():
    flow, root, child, grandchild, _ = _tree()

    with pytest.raises(CycleError):
        flow.reparent(child.id, grandchild.id)

    assert child in root.children          # unchanged


def test_reparent_refuses_a_full_if_node():
    flow, root, child, grandchild, other = _tree()
    target = _node("check", NodeType.IF)
    flow.graph.roots.append(target)
    flow.add_node(target.id)
    flow.add_node(target.id)

    with pytest.raises(MaxChildrenError):
        flow.reparent(child.id, target.id)

    assert child in root.children


def test_reparent_within_the_same_full_parent_reorders_instead_of_refusing():
    parent = _node("check", NodeType.IF)
    flow = FlowGraph(Graph(roots=[parent]))
    first  = flow.add_node(parent.id, name="first")
    second = flow.add_node(parent.id, name="second")

    flow.reparent(first.id, parent.id, index=1)

    assert parent.children == [second, first]


def test_reorder_swaps_two_siblings():
    flow, root, child, grandchild, other = _tree()

    flow.reorder(other.id, -1)

    assert flow.graph.roots == [other, root]
    assert flow.is_dirty is True


def test_reorder_at_the_edge_does_nothing_and_stays_clean():
    flow, root, child, grandchild, other = _tree()

    flow.reorder(root.id, -1)

    assert flow.graph.roots == [root, other]
    assert flow.is_dirty is False


def test_rename_node():
    flow, root, *_ = _tree()

    flow.rename_node(root.id, "renamed")

    assert root.name == "renamed"
    assert flow.is_dirty is True


def test_set_active_false_deactivates_the_whole_subtree():
    flow, root, child, grandchild, _ = _tree()

    flow.set_active(child.id, False)

    assert (child.is_active, grandchild.is_active) == (False, False)
    assert root.is_active is True
    assert flow.is_dirty is True


def test_set_active_true_reactivates_subtree_and_ancestors():
    flow, root, child, grandchild, _ = _tree()
    flow.set_active(root.id, False)

    flow.set_active(child.id, True)

    assert (root.is_active, child.is_active, grandchild.is_active) == (True, True, True)


def test_set_collapsed_marks_dirty_since_it_is_persisted():
    flow, root, *_ = _tree()

    flow.set_collapsed(root.id, True)

    assert root.is_collapsed is True
    assert flow.is_dirty is True


def test_set_executable():
    flow, root, *_ = _tree()

    flow.set_executable(root.id, True)

    assert root.is_executable is True
    assert flow.is_dirty is True


def test_generate_script_covers_the_whole_graph(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    text = flow.generate_script()

    assert text.startswith("#!/bin/bash")
    assert "echo un" in text
    assert "echo deux" in text
    assert "demo.flow" in text


def test_generate_script_from_a_node_stops_after_it(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    text = flow.generate_script(from_node_id=first.id)

    assert "echo un" in text
    assert "echo deux" not in text


def test_generate_script_does_not_touch_the_disk(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    flow.generate_script()

    assert list(tmp_path.glob("*.sh")) == []


def test_generate_script_on_an_unsaved_flow_names_it_untitled():
    flow = FlowGraph(Graph(roots=[_node("root")]))
    assert "sans-titre.flow" in flow.generate_script()


def test_write_script_writes_next_to_the_flow(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    path = flow.write_script()

    assert path == tmp_path / "demo.sh"
    assert path.exists()
    assert "echo deux" in path.read_text()


def test_write_run_script_is_timestamped_and_labelled(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    path = flow.write_run_script(from_node_id=first.id, timestamp="20260820-101500")

    assert path.name == "demo_first_20260820-101500.sh"
    assert "echo deux" not in path.read_text()


def test_write_run_script_without_a_target_has_no_label(tmp_path):
    flow, first, second = _script_flow(tmp_path)

    path = flow.write_run_script(timestamp="20260820-101500")

    assert path.name == "demo_20260820-101500.sh"


def test_write_script_on_an_unsaved_flow_raises():
    flow = FlowGraph(Graph(roots=[_node("root")]))
    with pytest.raises(ValueError):
        flow.write_script()


def test_run_writes_a_timestamped_script_and_launches_it(tmp_path, monkeypatch):
    flow, first, second = _script_flow(tmp_path)
    calls = []
    monkeypatch.setattr(
        "flower.engine.api.run_script",
        lambda path, terminal: calls.append((path, terminal)) or True,
    )

    assert flow.run(terminal="kitty") is True

    (path, terminal), = calls
    assert terminal == "kitty"
    assert path.exists()
    assert path.name.startswith("demo_")


def test_run_defaults_to_the_default_terminal(tmp_path, monkeypatch):
    flow, first, second = _script_flow(tmp_path)
    calls = []
    monkeypatch.setattr(
        "flower.engine.api.run_script",
        lambda path, terminal: calls.append((path, terminal)) or True,
    )

    flow.run()

    assert calls[0][1] == DEFAULT_TERMINAL


def test_run_reports_a_failed_launch(tmp_path, monkeypatch):
    flow, first, second = _script_flow(tmp_path)
    monkeypatch.setattr("flower.engine.api.run_script", lambda path, terminal: False)

    assert flow.run() is False


def test_run_from_an_unknown_node_raises(tmp_path):
    flow, first, second = _script_flow(tmp_path)
    with pytest.raises(ValueError):
        flow.run(from_node_id="absent")
