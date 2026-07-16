from __future__ import annotations
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Node, NodeType, Variable, VariableOperation
from flower.execution.traversal import traverse


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


def _script_body_lines(node: Node, interpreters: dict[str, str]) -> list[str]:
    """Lines to append after a node's block for its NodeType.SCRIPT body.
    Empty list if the node isn't a script node or has no body. bash (absent
    from `interpreters`) and any unrecognized/legacy language value fall
    back to inserting the body inline, with no heredoc."""
    if node.type != NodeType.SCRIPT:
        return []
    body = node.type_data.get("body", "").rstrip("\n")
    if not body:
        return []
    command = interpreters.get(node.type_data.get("language", ""))
    if command is None:
        return [body]
    delimiter = f"FL_SCRIPT_{node.id}"
    return [f"{command} <<'{delimiter}'", body, delimiter]


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

    for node in traverse(graph):
        lines.append("")
        lines.append(f"FL_NODE_NAME={_shell_quote(node.name)}")
        lines.append("echo Executing ${FL_NODE_NAME}")
        for v in node.variables:
            if v.active:
                lines.append(_declare_variable(v))
        lines.extend(_script_body_lines(node, interpreters))
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
