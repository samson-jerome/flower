import uuid
import os
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Node, NodeType, Variable, VariableOperation
from flower.execution.traversal import traverse
from flower.execution.bash_generator import (
    generate_bash_script, write_bash_script, write_timestamped_bash_script, _declare_variable,
)


def _node(name, **kwargs) -> Node:
    return Node(id=str(uuid.uuid4()), name=name, type=NodeType.NOOP, **kwargs)


def test_traverse_empty_graph_yields_nothing():
    assert list(traverse(Graph())) == []


def test_traverse_single_node():
    n = _node("solo")
    graph = Graph(roots=[n])
    assert list(traverse(graph)) == [n]


def test_traverse_preorder_parent_then_children_then_sibling():
    # root
    # ├── child_a
    # │   └── grandchild
    # └── child_b
    root       = _node("root")
    child_a    = _node("child_a")
    grandchild = _node("grandchild")
    child_b    = _node("child_b")
    child_a.children = [grandchild]
    grandchild.parent = child_a
    root.children = [child_a, child_b]
    child_a.parent = root
    child_b.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root", "child_a", "grandchild", "child_b"]


def test_traverse_multiple_roots_in_list_order():
    first  = _node("first")
    second = _node("second")
    graph = Graph(roots=[first, second])
    assert [n.name for n in traverse(graph)] == ["first", "second"]


def test_traverse_skips_inactive_node_and_its_subtree():
    root  = _node("root")
    child = _node("child", is_active=False)
    grandchild = _node("grandchild")
    child.children = [grandchild]
    grandchild.parent = child
    root.children = [child]
    child.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root"]


def test_traverse_visits_collapsed_node_children():
    root  = _node("root", is_collapsed=True)
    child = _node("child")
    root.children = [child]
    child.parent = root
    graph = Graph(roots=[root])

    assert [n.name for n in traverse(graph)] == ["root", "child"]


def test_generate_bash_script_empty_graph_has_only_shebang_and_flow_line():
    script = generate_bash_script(Graph(), "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
    )


def test_generate_bash_script_emits_shebang_first():
    script = generate_bash_script(Graph(), "demo.flow")
    assert script.startswith("#!/bin/bash\n")


def test_generate_bash_script_one_node():
    n = _node("build")
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='build'\n"
        "echo Executing ${FL_NODE_NAME}\n"
    )


def test_generate_bash_script_two_nodes_in_traversal_order():
    parent = _node("parent")
    child  = _node("child")
    parent.children = [child]
    child.parent = parent
    graph = Graph(roots=[parent])
    script = generate_bash_script(graph, "demo.flow")
    assert "FL_NODE_NAME='parent'" in script
    assert "FL_NODE_NAME='child'" in script
    assert script.index("FL_NODE_NAME='parent'") < script.index("FL_NODE_NAME='child'")


def test_generate_bash_script_escapes_single_quote_in_node_name():
    n = _node("it's a node")
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert "FL_NODE_NAME='it'\\''s a node'\n" in script


def test_generate_bash_script_escapes_single_quote_in_flow_name():
    script = generate_bash_script(Graph(), "it's.flow")
    assert "echo Executing flow 'it'\\''s.flow'\n" in script


def test_generate_bash_script_excludes_inactive_subtree():
    root  = _node("root")
    child = _node("child", is_active=False)
    root.children = [child]
    child.parent = root
    graph = Graph(roots=[root])
    script = generate_bash_script(graph, "demo.flow")
    assert "root" in script
    assert "child" not in script


def test_write_bash_script_creates_executable_file_next_to_flow(tmp_path):
    flow_path = tmp_path / "demo.flow"
    n = _node("build")
    graph = Graph(roots=[n])

    write_bash_script(graph, flow_path)

    script_path = tmp_path / "demo.sh"
    assert script_path.exists()
    assert os.access(script_path, os.X_OK)
    content = script_path.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/bash\n")
    assert "echo Executing flow 'demo.flow'" in content
    assert "FL_NODE_NAME='build'" in content


def test_write_bash_script_overwrites_existing_file(tmp_path):
    flow_path = tmp_path / "demo.flow"
    script_path = tmp_path / "demo.sh"
    script_path.write_text("stale content")

    write_bash_script(Graph(), flow_path)

    assert "stale content" not in script_path.read_text(encoding="utf-8")


def test_write_timestamped_bash_script_creates_file_with_timestamp_in_name(tmp_path):
    flow_path = tmp_path / "demo.flow"
    result_path = write_timestamped_bash_script(Graph(), flow_path, "20260702-143022")
    expected_path = tmp_path / "demo_20260702-143022.sh"
    assert result_path == expected_path
    assert expected_path.exists()


def test_write_timestamped_bash_script_content_matches_generate_bash_script(tmp_path):
    flow_path = tmp_path / "demo.flow"
    n = _node("build")
    graph = Graph(roots=[n])
    result_path = write_timestamped_bash_script(graph, flow_path, "20260702-143022")
    content = result_path.read_text(encoding="utf-8")
    assert content == generate_bash_script(graph, "demo.flow")


def test_write_timestamped_bash_script_is_executable(tmp_path):
    flow_path = tmp_path / "demo.flow"
    result_path = write_timestamped_bash_script(Graph(), flow_path, "20260702-143022")
    assert os.access(result_path, os.X_OK)


def test_write_timestamped_bash_script_does_not_touch_static_script(tmp_path):
    flow_path = tmp_path / "demo.flow"
    write_bash_script(Graph(), flow_path)
    static_content_before = (tmp_path / "demo.sh").read_text(encoding="utf-8")

    write_timestamped_bash_script(Graph(), flow_path, "20260702-143022")

    assert (tmp_path / "demo.sh").read_text(encoding="utf-8") == static_content_before
    assert (tmp_path / "demo_20260702-143022.sh").exists()


def test_declare_variable_assign():
    v = Variable(name="ENV", value="prod", operation=VariableOperation.ASSIGN)
    assert _declare_variable(v) == "ENV='prod'"


def test_declare_variable_concat():
    v = Variable(name="MSG", value="world", operation=VariableOperation.CONCAT)
    assert _declare_variable(v) == "MSG+='world'"


def test_declare_variable_add():
    v = Variable(name="COUNT", value="1", operation=VariableOperation.ADD)
    assert _declare_variable(v) == "COUNT=$((COUNT + 1))"


def test_declare_variable_unknown_operation_falls_back_to_assign():
    v = Variable(name="ENV", value="prod", operation="unknown")
    assert _declare_variable(v) == "ENV='prod'"


def test_generate_bash_script_includes_active_global_variable():
    graph = Graph(variables=[Variable(name="ENV", value="prod")])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "ENV='prod'\n"
    )


def test_generate_bash_script_excludes_inactive_global_variable():
    graph = Graph(variables=[Variable(name="ENV", value="prod", active=False)])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
    )


def test_generate_bash_script_includes_active_local_variable():
    n = _node("build", variables=[Variable(name="TARGET", value="release")])
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='build'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "TARGET='release'\n"
    )


def test_generate_bash_script_excludes_inactive_local_variable():
    n = _node("build", variables=[Variable(name="TARGET", value="release", active=False)])
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert "TARGET" not in script


def test_generate_bash_script_global_and_local_variables_combined():
    n = _node("build", variables=[Variable(name="TARGET", value="release")])
    graph = Graph(roots=[n], variables=[Variable(name="ENV", value="prod")])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "ENV='prod'\n"
        "\n"
        "FL_NODE_NAME='build'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "TARGET='release'\n"
    )


def test_generate_bash_script_concat_and_add_operations():
    n = _node("build", variables=[
        Variable(name="MSG", value="world", operation=VariableOperation.CONCAT),
        Variable(name="COUNT", value="1", operation=VariableOperation.ADD),
    ])
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert "MSG+='world'\n" in script
    assert "COUNT=$((COUNT + 1))\n" in script
