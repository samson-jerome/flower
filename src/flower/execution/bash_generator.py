from __future__ import annotations
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Node, NodeType, Variable, VariableOperation


def _shell_quote(value: str) -> str:
    """Wrap value in single quotes for safe literal interpolation in bash,
    escaping any embedded single quote as '\\''."""
    return "'" + value.replace("'", "'\\''") + "'"


def _declare_variable(var: Variable) -> str:
    """Bash declaration line for one active variable, per its operation,
    followed by an export line so the variable is visible in the
    environment of any external interpreter invoked via heredoc (see
    _script_body_lines). Any operation value other than CONCAT/ADD
    (including unrecognized legacy values) is treated as ASSIGN."""
    if var.operation == VariableOperation.CONCAT:
        assignment = f"{var.name}+={_shell_quote(var.value)}"
    elif var.operation == VariableOperation.ADD:
        assignment = f"{var.name}=$(({var.name} + {var.value}))"
    else:
        assignment = f"{var.name}={_shell_quote(var.value)}"
    return f"{assignment}\nexport {var.name}"


DEFAULT_INTERPRETERS: dict[str, str] = {
    "sh":         "sh",
    "python":     "python3",
    "powershell": "pwsh",
    "javascript": "node",
}


def _script_body_lines(node: Node, interpreters: dict[str, str], pad: str = "") -> list[str]:
    """Lines to append after a node's block for its NodeType.SCRIPT body.
    Empty list if the node isn't a script node or has no body. bash (absent
    from `interpreters`) and any unrecognized/legacy language value fall
    back to inserting the body inline, with no heredoc. `pad` is applied
    only to the heredoc's opening command line -- never to `body` or the
    closing `delimiter` line, since indenting either could corrupt
    whitespace-significant body content or break the heredoc's terminator
    recognition (which requires column 0)."""
    if node.type != NodeType.SCRIPT:
        return []
    body = node.type_data.get("body", "").rstrip("\n")
    if not body:
        return []
    command = interpreters.get(node.type_data.get("language", ""))
    if command is None:
        return [body]
    delimiter = f"FL_SCRIPT_{node.id}"
    return [f"{pad}{command} <<'{delimiter}'", body, delimiter]


def _loop_index(node: Node) -> str:
    """Loop variable name for a LOOP node, falling back to a generated one
    when the user left the field empty -- an empty name would produce
    invalid bash and break the whole script."""
    return node.type_data.get("index", "") or "FL_LOOP_INDEX"


def _loop_header(node: Node) -> str:
    """The `for ...; do` line for a LOOP node. Builds a C-style arithmetic
    loop with an inclusive upper bound, so start > end simply yields no
    iteration -- no guard needed. Any mode value other than "list"
    (including unrecognized legacy values) is treated as range, matching
    LoopEditor.set_data()."""
    index = _loop_index(node)
    start = node.type_data.get("start", 0)
    end   = node.type_data.get("end", 0)
    step  = node.type_data.get("step", 1)
    return f"for (({index}={start}; {index}<={end}; {index}+={step})); do"


def _generate_node(
    node: Node, interpreters: dict[str, str], indent: int = 0, leading_blank: bool = True,
) -> list[str]:
    """Lines for `node` and its subtree. Empty list if `node.is_active` is
    False (its whole subtree is skipped, matching traverse()'s former
    semantics). `indent` is the nesting depth in 4-space units, incremented
    only when descending into an IF node's then/else block -- plain
    parent/child sequencing (non-IF) stays at the same depth, matching the
    flat, unindented output this replaces. `leading_blank` adds the blank
    separator line used between flat sibling blocks; it is False for the
    first node of a then/else branch, since the if/else line itself already
    marks the start of that block. Only ever reads children[0]/children[1]
    for an IF node -- any child beyond index 1 is silently ignored (the UI
    prevents an IF node from having more than 2 children in the first
    place; see MAX_CHILDREN in models/node.py)."""
    if not node.is_active:
        return []
    pad = "    " * indent
    lines = [""] if leading_blank else []
    lines.append(f"{pad}FL_NODE_NAME={_shell_quote(node.name)}")
    lines.append(f"{pad}echo Executing ${{FL_NODE_NAME}}")
    for v in node.variables:
        if v.active:
            lines.append("\n".join(pad + line for line in _declare_variable(v).split("\n")))

    if node.type == NodeType.IF:
        condition = node.type_data.get("condition", "")
        lines.append(f"{pad}if [ {condition} ]; then")
        true_lines = (
            _generate_node(node.children[0], interpreters, indent + 1, leading_blank=False)
            if node.children else []
        )
        lines.extend(true_lines if true_lines else [f"{pad}    :"])
        false_lines = (
            _generate_node(node.children[1], interpreters, indent + 1, leading_blank=False)
            if len(node.children) > 1 else []
        )
        if false_lines:
            lines.append(f"{pad}else")
            lines.extend(false_lines)
        lines.append(f"{pad}fi")
    else:
        lines.extend(_script_body_lines(node, interpreters, pad))
        for child in node.children:
            lines.extend(_generate_node(child, interpreters, indent))
    return lines


def generate_bash_script(
    graph: Graph, flow_name: str, interpreters: dict[str, str] | None = None
) -> str:
    """Build the full script text for `graph`. `flow_name` is the display
    name of the .flow file (e.g. "demo.flow"), echoed once before any node.
    `interpreters` maps a script node's language (sh/python/powershell/
    javascript) to the shell command invoked via heredoc; defaults to
    DEFAULT_INTERPRETERS when None. Pure function — no filesystem access.
    """
    interpreters = interpreters if interpreters is not None else DEFAULT_INTERPRETERS
    lines = ["#!/bin/bash", "", f"echo Executing flow {_shell_quote(flow_name)}"]

    active_global_vars = [v for v in graph.variables if v.active]
    if active_global_vars:
        lines.append("")
        for v in active_global_vars:
            lines.append(_declare_variable(v))

    for root in graph.roots:
        lines.extend(_generate_node(root, interpreters))
    return "\n".join(lines) + "\n"


def _write_script(text: str, script_path: Path) -> None:
    script_path.write_text(text, encoding="utf-8")
    script_path.chmod(0o755)


def write_bash_script(
    graph: Graph, flow_path: Path, interpreters: dict[str, str] | None = None
) -> None:
    """Generate the script for `graph` and write it next to `flow_path`
    (same file name, .sh extension), then make it executable."""
    _write_script(
        generate_bash_script(graph, flow_path.name, interpreters), flow_path.with_suffix(".sh")
    )


def write_timestamped_bash_script(
    graph: Graph, flow_path: Path, timestamp: str, interpreters: dict[str, str] | None = None
) -> Path:
    """Same content as write_bash_script, written to <stem>_<timestamp>.sh
    next to flow_path. Returns the path written, so the caller knows what
    to execute. `timestamp` is injected by the caller (not computed here)
    to keep this function deterministic and testable."""
    script_path = flow_path.with_name(f"{flow_path.stem}_{timestamp}.sh")
    _write_script(generate_bash_script(graph, flow_path.name, interpreters), script_path)
    return script_path
