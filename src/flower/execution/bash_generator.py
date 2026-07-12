from __future__ import annotations
from pathlib import Path
from flower.models.graph import Graph
from flower.models.node import Variable, VariableOperation
from flower.execution.traversal import traverse


def _shell_quote(value: str) -> str:
    """Wrap value in single quotes for safe literal interpolation in bash,
    escaping any embedded single quote as '\\''."""
    return "'" + value.replace("'", "'\\''") + "'"


def _declare_variable(var: Variable) -> str:
    """Bash declaration line for one active variable, per its operation.
    Any operation value other than CONCAT/ADD (including unrecognized
    legacy values) is treated as ASSIGN."""
    if var.operation == VariableOperation.CONCAT:
        return f"{var.name}+={_shell_quote(var.value)}"
    if var.operation == VariableOperation.ADD:
        return f"{var.name}=$(({var.name} + {var.value}))"
    return f"{var.name}={_shell_quote(var.value)}"


def generate_bash_script(graph: Graph, flow_name: str) -> str:
    """Build the full script text for `graph`. `flow_name` is the display
    name of the .flow file (e.g. "demo.flow"), echoed once before any node.
    Pure function — no filesystem access.
    """
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
    return "\n".join(lines) + "\n"


def _write_script(text: str, script_path: Path) -> None:
    script_path.write_text(text, encoding="utf-8")
    script_path.chmod(0o755)


def write_bash_script(graph: Graph, flow_path: Path) -> None:
    """Generate the script for `graph` and write it next to `flow_path`
    (same file name, .sh extension), then make it executable."""
    _write_script(generate_bash_script(graph, flow_path.name), flow_path.with_suffix(".sh"))


def write_timestamped_bash_script(graph: Graph, flow_path: Path, timestamp: str) -> Path:
    """Same content as write_bash_script, written to <stem>_<timestamp>.sh
    next to flow_path. Returns the path written, so the caller knows what
    to execute. `timestamp` is injected by the caller (not computed here)
    to keep this function deterministic and testable."""
    script_path = flow_path.with_name(f"{flow_path.stem}_{timestamp}.sh")
    _write_script(generate_bash_script(graph, flow_path.name), script_path)
    return script_path
