from __future__ import annotations
from pathlib import Path
from flower.models.graph import Graph
from flower.execution.traversal import traverse


def _shell_quote(value: str) -> str:
    """Wrap value in single quotes for safe literal interpolation in bash,
    escaping any embedded single quote as '\\''."""
    return "'" + value.replace("'", "'\\''") + "'"


def generate_bash_script(graph: Graph, flow_name: str) -> str:
    """Build the full script text for `graph`. `flow_name` is the display
    name of the .flow file (e.g. "demo.flow"), echoed once before any node.
    Pure function — no filesystem access.
    """
    lines = ["#!/bin/bash", "", f"echo Executing flow {_shell_quote(flow_name)}"]
    for node in traverse(graph):
        lines.append("")
        lines.append(f"FL_NODE_NAME={_shell_quote(node.name)}")
        lines.append("echo Executing ${FL_NODE_NAME}")
    return "\n".join(lines) + "\n"


def write_bash_script(graph: Graph, flow_path: Path) -> None:
    """Generate the script for `graph` and write it next to `flow_path`
    (same file name, .sh extension), then make it executable."""
    script_path = flow_path.with_suffix(".sh")
    script_path.write_text(generate_bash_script(graph, flow_path.name), encoding="utf-8")
    script_path.chmod(0o755)
