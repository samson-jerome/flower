from __future__ import annotations
import shlex
from pathlib import Path
from PySide6.QtCore import QProcess


def launch_in_terminal(script_path: Path) -> None:
    """Open a new detached terminal window running script_path, then drop
    into an interactive shell so the output stays visible afterward.

    Linux only: relies on x-terminal-emulator, the Debian/Ubuntu alternative
    for the system's configured default terminal. Per Debian Policy, every
    registered alternative must support `-e <program> <args...>` — passed
    here as separate argv elements rather than one shell-parsed string, so
    behavior does not depend on the target terminal's own quoting rules.
    """
    command = f"{shlex.quote(str(script_path))}; exec bash"
    QProcess.startDetached("x-terminal-emulator", ["-e", "bash", "-c", command])
