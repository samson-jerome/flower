import uuid
import os
import subprocess
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Node, NodeType, Variable, VariableOperation
from flower.execution.traversal import traverse
from flower.execution.bash_generator import (
    generate_bash_script, write_bash_script, write_timestamped_bash_script,
    _declare_variable, _script_body_lines, _loop_index, _loop_header,
    DEFAULT_INTERPRETERS,
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


def _loop_node(name, type_data=None, node_id=None, **kwargs) -> Node:
    return Node(
        id=node_id or str(uuid.uuid4()), name=name, type=NodeType.LOOP,
        type_data=type_data or {}, **kwargs
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


def test_generate_bash_script_if_node_inactive_false_child_treated_as_absent():
    true_child  = _node("deploy")
    false_child = _node("rollback", is_active=False)
    if_node = _if_node("check", "-f /tmp/flag", children=[true_child, false_child])
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
        "if [ -f /tmp/flag ]; then\n"
        "    FL_NODE_NAME='deploy'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
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


def test_loop_index_returns_field_value():
    assert _loop_index(_loop_node("iter", {"index": "f"})) == "f"


def test_loop_index_falls_back_when_empty():
    assert _loop_index(_loop_node("iter", {"index": ""})) == "FL_LOOP_INDEX"


def test_loop_index_falls_back_when_absent():
    assert _loop_index(_loop_node("iter")) == "FL_LOOP_INDEX"


def test_loop_header_range_with_explicit_bounds():
    n = _loop_node("iter", {"index": "i", "mode": "range", "start": 0, "end": 10, "step": 2})
    assert _loop_header(n) == "for ((i=0; i<=10; i+=2)); do"


def test_loop_header_range_defaults_on_empty_type_data():
    n = _loop_node("iter")
    assert _loop_header(n) == (
        "for ((FL_LOOP_INDEX=0; FL_LOOP_INDEX<=0; FL_LOOP_INDEX+=1)); do"
    )


def test_loop_header_range_empty_index_uses_fallback():
    n = _loop_node("iter", {"index": "", "mode": "range", "start": 1, "end": 3, "step": 1})
    assert _loop_header(n) == (
        "for ((FL_LOOP_INDEX=1; FL_LOOP_INDEX<=3; FL_LOOP_INDEX+=1)); do"
    )


def test_loop_header_range_start_greater_than_end_is_emitted_as_is():
    # No iteration at runtime; the C-style form makes this safe without a guard.
    n = _loop_node("iter", {"index": "i", "mode": "range", "start": 10, "end": 0, "step": 1})
    assert _loop_header(n) == "for ((i=10; i<=0; i+=1)); do"


def test_loop_header_unknown_mode_treated_as_range():
    n = _loop_node("iter", {"index": "i", "mode": "legacy", "start": 0, "end": 2, "step": 1})
    assert _loop_header(n) == "for ((i=0; i<=2; i+=1)); do"


def test_loop_header_list_quotes_each_item():
    n = _loop_node("files", {
        "index": "f", "mode": "list", "items": "a.txt\nrapport final.txt",
    })
    assert _loop_header(n) == "for f in 'a.txt' 'rapport final.txt'; do"


def test_loop_header_list_skips_blank_lines_and_strips_edges():
    n = _loop_node("files", {
        "index": "f", "mode": "list", "items": "  a.txt  \n\n   \nb.txt\n",
    })
    assert _loop_header(n) == "for f in 'a.txt' 'b.txt'; do"


def test_loop_header_list_empty_items_yields_empty_word_list():
    # `for f in ; do ... done` is valid bash and never iterates.
    n = _loop_node("files", {"index": "f", "mode": "list", "items": ""})
    assert _loop_header(n) == "for f in ; do"


def test_loop_header_list_only_blank_lines_yields_empty_word_list():
    n = _loop_node("files", {"index": "f", "mode": "list", "items": "\n   \n\n"})
    assert _loop_header(n) == "for f in ; do"


def test_loop_header_list_escapes_single_quote():
    n = _loop_node("files", {"index": "f", "mode": "list", "items": "l'été"})
    assert _loop_header(n) == "for f in 'l'\\''été'; do"


def test_loop_header_list_keeps_expansions_literal():
    n = _loop_node("files", {"index": "f", "mode": "list", "items": "$HOME/data\n*.log"})
    assert _loop_header(n) == "for f in '$HOME/data' '*.log'; do"


def test_loop_header_list_empty_index_uses_fallback():
    n = _loop_node("files", {"index": "", "mode": "list", "items": "a"})
    assert _loop_header(n) == "for FL_LOOP_INDEX in 'a'; do"


def test_loop_header_expression_wraps_command_substitution():
    n = _loop_node("files", {"index": "f", "mode": "expression", "expression": "ls"})
    assert _loop_header(n) == "for f in $(ls); do"


def test_loop_header_expression_keeps_globs_and_tilde_unquoted():
    # The exact opposite of list mode: bash must expand these at runtime.
    n = _loop_node("files", {"index": "f", "mode": "expression", "expression": "ls ~/*.*"})
    assert _loop_header(n) == "for f in $(ls ~/*.*); do"


def test_loop_header_expression_keeps_pipes_verbatim():
    n = _loop_node("files", {
        "index": "f", "mode": "expression", "expression": "find . -name '*.log' | sort",
    })
    assert _loop_header(n) == "for f in $(find . -name '*.log' | sort); do"


def test_loop_header_expression_does_not_escape_single_quotes():
    # Unlike list mode, quotes are the user's own bash syntax, not data.
    n = _loop_node("files", {
        "index": "f", "mode": "expression", "expression": 'echo "l\'été"',
    })
    assert _loop_header(n) == 'for f in $(echo "l\'été"); do'


def test_loop_header_expression_keeps_internal_newlines():
    n = _loop_node("files", {
        "index": "f", "mode": "expression", "expression": "find . -name '*.log' \\\n  | sort",
    })
    assert _loop_header(n) == "for f in $(find . -name '*.log' \\\n  | sort); do"


def test_loop_header_expression_strips_surrounding_whitespace():
    # A QTextEdit readily leaves a trailing newline behind.
    n = _loop_node("files", {"index": "f", "mode": "expression", "expression": "  ls -1\n\n"})
    assert _loop_header(n) == "for f in $(ls -1); do"


def test_loop_header_expression_empty_yields_empty_substitution():
    # `for f in $(); do ... done` is valid bash and never iterates.
    n = _loop_node("files", {"index": "f", "mode": "expression", "expression": ""})
    assert _loop_header(n) == "for f in $(); do"


def test_loop_header_expression_missing_key_yields_empty_substitution():
    n = _loop_node("files", {"index": "f", "mode": "expression"})
    assert _loop_header(n) == "for f in $(); do"


def test_loop_header_expression_empty_index_uses_fallback():
    n = _loop_node("files", {"index": "", "mode": "expression", "expression": "ls"})
    assert _loop_header(n) == "for FL_LOOP_INDEX in $(ls); do"


def test_generate_bash_script_loop_range_with_one_child():
    child = _node("étape")
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 4, "step": 2},
        children=[child],
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=4; i+=2)); do\n"
        "    export i\n"
        "    FL_NODE_NAME='étape'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "done\n"
    )


def test_generate_bash_script_loop_list_with_one_child():
    child = _node("traiter")
    loop = _loop_node(
        "fichiers", {"index": "f", "mode": "list", "items": "a.txt\nrapport final.txt"},
        children=[child],
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='fichiers'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for f in 'a.txt' 'rapport final.txt'; do\n"
        "    export f\n"
        "    FL_NODE_NAME='traiter'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "done\n"
    )


def test_generate_bash_script_loop_expression_with_one_child():
    child = _node("traiter")
    loop = _loop_node(
        "fichiers", {"index": "f", "mode": "expression", "expression": "ls ~/*.*"},
        children=[child],
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='fichiers'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for f in $(ls ~/*.*); do\n"
        "    export f\n"
        "    FL_NODE_NAME='traiter'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "done\n"
    )


def test_generate_bash_script_loop_expression_with_script_child():
    # The heredoc's opening line follows the indentation; its body and closing
    # delimiter must stay at column 0 or bash swallows the rest of the file.
    child = _script_node(
        "traiter", "python", 'import os\nprint(os.environ["f"])', node_id="SID",
    )
    loop = _loop_node(
        "fichiers", {"index": "f", "mode": "expression", "expression": "ls"},
        children=[child],
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='fichiers'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for f in $(ls); do\n"
        "    export f\n"
        "    FL_NODE_NAME='traiter'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "    python3 <<'FL_SCRIPT_SID'\n"
        "import os\n"
        'print(os.environ["f"])\n'
        "FL_SCRIPT_SID\n"
        "done\n"
    )


def test_generate_bash_script_loop_no_children_needs_no_colon_filler():
    # `export` alone keeps the do...done body non-empty, so unlike an empty
    # conditional branch this needs no `:` no-op.
    loop = _loop_node("iter", {"index": "i", "mode": "range", "start": 0, "end": 2, "step": 1})
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=2; i+=1)); do\n"
        "    export i\n"
        "done\n"
    )


def test_generate_bash_script_loop_inactive_child_treated_as_absent():
    child = _node("étape", is_active=False)
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 2, "step": 1},
        children=[child],
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=2; i+=1)); do\n"
        "    export i\n"
        "done\n"
    )


def test_generate_bash_script_loop_two_children_blank_line_between_only():
    first  = _node("a")
    second = _node("b")
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[first, second],
    )
    first.parent = loop
    second.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=1; i+=1)); do\n"
        "    export i\n"
        "    FL_NODE_NAME='a'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "\n"
        "    FL_NODE_NAME='b'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "done\n"
    )


def test_generate_bash_script_loop_variables_declared_once_before_for():
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        variables=[Variable(name="ROOT", value="/tmp")],
    )
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "ROOT='/tmp'\n"
        "export ROOT\n"
        "for ((i=0; i<=1; i+=1)); do\n"
        "    export i\n"
        "done\n"
    )


def test_generate_bash_script_inactive_loop_emits_nothing():
    child = _node("étape")
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[child], is_active=False,
    )
    child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
    )


def test_generate_bash_script_nested_loop_doubles_indentation():
    inner_child = _node("corps")
    inner = _loop_node(
        "inner", {"index": "j", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[inner_child],
    )
    inner_child.parent = inner
    outer = _loop_node(
        "outer", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[inner],
    )
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
        "for ((i=0; i<=1; i+=1)); do\n"
        "    export i\n"
        "    FL_NODE_NAME='inner'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "    for ((j=0; j<=1; j+=1)); do\n"
        "        export j\n"
        "        FL_NODE_NAME='corps'\n"
        "        echo Executing ${FL_NODE_NAME}\n"
        "    done\n"
        "done\n"
    )


def test_generate_bash_script_heredoc_in_loop_body_and_delimiter_not_indented():
    # The closing heredoc delimiter must sit at column 0 or bash swallows the
    # rest of the file -- so only the opening command line follows the padding.
    script_child = _script_node("build", "python", "print('hi')", node_id="abc123")
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[script_child],
    )
    script_child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=1; i+=1)); do\n"
        "    export i\n"
        "    FL_NODE_NAME='build'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "    python3 <<'FL_SCRIPT_abc123'\n"
        "print('hi')\n"
        "FL_SCRIPT_abc123\n"
        "done\n"
    )


def test_generate_bash_script_inline_script_body_not_indented_in_loop():
    script_child = _script_node("build", "bash", "echo hi")
    loop = _loop_node(
        "iter", {"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1},
        children=[script_child],
    )
    script_child.parent = loop
    graph = Graph(roots=[loop])
    script = generate_bash_script(graph, "demo.flow")
    assert script == (
        "#!/bin/bash\n"
        "\n"
        "echo Executing flow 'demo.flow'\n"
        "\n"
        "FL_NODE_NAME='iter'\n"
        "echo Executing ${FL_NODE_NAME}\n"
        "for ((i=0; i<=1; i+=1)); do\n"
        "    export i\n"
        "    FL_NODE_NAME='build'\n"
        "    echo Executing ${FL_NODE_NAME}\n"
        "echo hi\n"
        "done\n"
    )


def test_generated_loop_script_passes_bash_syntax_check(tmp_path):
    empty_range = _loop_node(
        "vide", {"index": "k", "mode": "range", "start": 0, "end": 1, "step": 1},
    )
    inner = _loop_node(
        "inner", {"index": "j", "mode": "range", "start": 0, "end": 2, "step": 1},
        children=[empty_range],
    )
    empty_range.parent = inner

    list_child = _script_node("traiter", "python", 'import os\nprint(os.environ["f"])')
    list_loop = _loop_node(
        "fichiers",
        {"index": "f", "mode": "list", "items": "rapport final.txt\nl'été\n$HOME/x"},
        children=[list_child],
    )
    list_child.parent = list_loop

    empty_list = _loop_node("aucun", {"index": "g", "mode": "list", "items": ""})

    expr_child = _script_node("lire", "bash", 'echo "$h"')
    expr_loop = _loop_node(
        "calculé",
        {"index": "h", "mode": "expression", "expression": "ls ~/*.* \\\n  | sort"},
        children=[expr_child],
    )
    expr_child.parent = expr_loop

    empty_expr = _loop_node("rien", {"index": "e", "mode": "expression", "expression": ""})

    outer = _loop_node(
        "outer", {"index": "i", "mode": "range", "start": 0, "end": 2, "step": 1},
        children=[inner, list_loop, empty_list, expr_loop, empty_expr],
    )
    for child in outer.children:
        child.parent = outer

    graph = Graph(roots=[outer])
    flow_path = tmp_path / "demo.flow"
    write_bash_script(graph, flow_path)

    result = subprocess.run(
        ["bash", "-n", str(flow_path.with_suffix(".sh"))],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
