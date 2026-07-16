import uuid
import os
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Node, NodeType, Variable, VariableOperation
from flower.execution.traversal import traverse
from flower.execution.bash_generator import (
    generate_bash_script, write_bash_script, write_timestamped_bash_script,
    _declare_variable, _script_body_lines, DEFAULT_INTERPRETERS,
)


def _node(name, **kwargs) -> Node:
    return Node(id=str(uuid.uuid4()), name=name, type=NodeType.NOOP, **kwargs)


def _script_node(name, language, body, node_id=None, **kwargs) -> Node:
    return Node(
        id=node_id or str(uuid.uuid4()), name=name, type=NodeType.SCRIPT,
        type_data={"language": language, "body": body}, **kwargs
    )


def _if_node(name, condition, node_id=None, **kwargs) -> Node:
    return Node(
        id=node_id or str(uuid.uuid4()), name=name, type=NodeType.IF,
        type_data={"condition": condition}, **kwargs
    )


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
    assert _declare_variable(v) == "ENV='prod'\nexport ENV"


def test_declare_variable_concat():
    v = Variable(name="MSG", value="world", operation=VariableOperation.CONCAT)
    assert _declare_variable(v) == "MSG+='world'\nexport MSG"


def test_declare_variable_add():
    v = Variable(name="COUNT", value="1", operation=VariableOperation.ADD)
    assert _declare_variable(v) == "COUNT=$((COUNT + 1))\nexport COUNT"


def test_declare_variable_unknown_operation_falls_back_to_assign():
    v = Variable(name="ENV", value="prod", operation="unknown")
    assert _declare_variable(v) == "ENV='prod'\nexport ENV"


def test_generate_bash_script_includes_active_global_variable():
    graph = Graph(variables=[Variable(name="ENV", value="prod")])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "ENV='prod'\n"
        "export ENV\n"
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
        "export TARGET\n"
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
        "export ENV\n"
        "\n"
        "FL_NODE_NAME='build'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "TARGET='release'\n"
        "export TARGET\n"
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


def test_generate_bash_script_exports_variables_for_external_interpreters():
    # Variables must be exported (not just assigned) so that an external
    # interpreter invoked via heredoc (see _script_body_lines) can see them
    # in its own process environment (os.environ, $env:, process.env, ...).
    n = _script_node("build", "python", "print(1)", node_id="node1",
                      variables=[Variable(name="TARGET", value="release")])
    graph = Graph(roots=[n], variables=[Variable(name="ENV", value="prod")])
    script = generate_bash_script(graph, "demo.flow")
    assert "ENV='prod'\nexport ENV\n" in script
    assert "TARGET='release'\nexport TARGET\n" in script


def test_script_body_lines_bash_is_inline():
    n = _script_node("build", "bash", "echo hello")
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == ["echo hello"]


def test_script_body_lines_empty_body_yields_nothing():
    n = _script_node("build", "bash", "")
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == []


def test_script_body_lines_non_script_node_yields_nothing():
    n = _node("build")
    n.type_data = {"language": "python", "body": "print(1)"}
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == []


def test_script_body_lines_python_uses_heredoc_with_configured_command():
    n = _script_node("build", "python", "print('hi')", node_id="abc-123")
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == [
        "python3 <<'FL_SCRIPT_abc-123'",
        "print('hi')",
        "FL_SCRIPT_abc-123",
    ]


def test_script_body_lines_unknown_language_falls_back_to_inline():
    n = _script_node("build", "ruby", "puts 1")
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == ["puts 1"]


def test_script_body_lines_uses_custom_interpreter_override():
    n = _script_node("build", "python", "print(1)", node_id="xyz")
    custom = {**DEFAULT_INTERPRETERS, "python": "/usr/bin/python3.11"}
    lines = _script_body_lines(n, custom)
    assert lines[0] == "/usr/bin/python3.11 <<'FL_SCRIPT_xyz'"


def test_script_body_lines_strips_trailing_newline():
    n = _script_node("build", "bash", "echo hi\n")
    assert _script_body_lines(n, DEFAULT_INTERPRETERS) == ["echo hi"]


def test_generate_bash_script_includes_script_body_after_variables():
    n = _script_node("build", "bash", "echo hi", variables=[Variable(name="TARGET", value="release")])
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
        "export TARGET\n"
        "echo hi\n"
    )


def test_generate_bash_script_uses_custom_interpreters_argument():
    n = _script_node("build", "javascript", "console.log(1)", node_id="node1")
    graph = Graph(roots=[n])
    custom = {**DEFAULT_INTERPRETERS, "javascript": "nodejs"}
    script = generate_bash_script(graph, "demo.flow", interpreters=custom)
    assert "nodejs <<'FL_SCRIPT_node1'" in script


def test_generate_bash_script_default_interpreters_used_when_not_passed():
    n = _script_node("build", "python", "print(1)", node_id="node2")
    graph = Graph(roots=[n])
    script = generate_bash_script(graph, "demo.flow")
    assert "python3 <<'FL_SCRIPT_node2'" in script


def test_generate_bash_script_empty_script_body_adds_nothing():
    n = _script_node("build", "bash", "")
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


def test_generate_bash_script_if_node_true_and_false_branches():
    true_child  = _node("deploy")
    false_child = _node("rollback")
    if_node = _if_node("check", '"$TARGET" = "release"', children=[true_child, false_child])
    true_child.parent = if_node
    false_child.parent = if_node
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ \"$TARGET\" = \"release\" ]; then\n"
        "    FL_NODE_NAME='deploy'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "else\n"
        "    FL_NODE_NAME='rollback'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "fi\n"
    )


def test_generate_bash_script_if_node_true_branch_only():
    true_child = _node("deploy")
    if_node = _if_node("check", "-f /tmp/flag", children=[true_child])
    true_child.parent = if_node
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/flag ]; then\n"
        "    FL_NODE_NAME='deploy'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "fi\n"
    )


def test_generate_bash_script_if_node_no_children():
    if_node = _if_node("check", "-f /tmp/flag")
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/flag ]; then\n"
        "    :\n"
        "fi\n"
    )


def test_generate_bash_script_if_node_inactive_true_child_treated_as_absent():
    true_child = _node("deploy", is_active=False)
    if_node = _if_node("check", "-f /tmp/flag", children=[true_child])
    true_child.parent = if_node
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/flag ]; then\n"
        "    :\n"
        "fi\n"
    )


def test_generate_bash_script_if_node_empty_condition():
    if_node = _if_node("check", "")
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [  ]; then\n"
        "    :\n"
        "fi\n"
    )


def test_generate_bash_script_if_node_variables_declared_before_condition():
    if_node = _if_node(
        "check", '"$TARGET" = "release"',
        variables=[Variable(name="TARGET", value="release")],
    )
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "TARGET='release'\n"
        "export TARGET\n"
        "if [ \"$TARGET\" = \"release\" ]; then\n"
        "    :\n"
        "fi\n"
    )


def test_generate_bash_script_nested_if_doubles_indentation():
    leaf  = _node("leaf")
    inner = _if_node("inner", "-f /tmp/b", children=[leaf])
    leaf.parent = inner
    outer = _if_node("outer", "-f /tmp/a", children=[inner])
    inner.parent = outer
    graph = Graph(roots=[outer])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='outer'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/a ]; then\n"
        "    FL_NODE_NAME='inner'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "    if [ -f /tmp/b ]; then\n"
        "        FL_NODE_NAME='leaf'\n"
        "        echo Executing ${FL_NODE_NAME}\n"
        "    fi\n"
        "fi\n"
    )


def test_generate_bash_script_inline_script_body_not_indented_inside_branch():
    script_child = _script_node("build", "bash", "echo hi")
    if_node = _if_node("check", "-f /tmp/flag", children=[script_child])
    script_child.parent = if_node
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/flag ]; then\n"
        "    FL_NODE_NAME='build'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "echo hi\n"
        "fi\n"
    )


def test_generate_bash_script_heredoc_command_indented_but_body_and_delimiter_not():
    script_child = _script_node("build", "python", "print('hi')", node_id="abc123")
    if_node = _if_node("check", "-f /tmp/flag", children=[script_child])
    script_child.parent = if_node
    graph = Graph(roots=[if_node])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='check'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "if [ -f /tmp/flag ]; then\n"
        "    FL_NODE_NAME='build'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "    python3 <<'FL_SCRIPT_abc123'\n"
        "print('hi')\n"
        "FL_SCRIPT_abc123\n"
        "fi\n"
    )


def test_generate_bash_script_no_regression_without_if_nodes():
    # Same tree shape as test_traverse_preorder_parent_then_children_then_sibling.
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

    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='root'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "\n"
        "FL_NODE_NAME='child_a'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "\n"
        "FL_NODE_NAME='grandchild'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "\n"
        "FL_NODE_NAME='child_b'\n"
        "echo Executing ${FL_NODE_NAME}\n"
    )
