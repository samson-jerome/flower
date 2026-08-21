from __future__ import annotations
import shlex
import subprocess
from pathlib import Path

DEFAULT_TERMINAL = "x-terminal-emulator"

# Terminals started so far, kept only to poll() them on the next launch.
# Popen keeps this process as their parent, so a terminal the user closes
# would stay a zombie until the application exits; poll() reaps it.
_running: list[subprocess.Popen] = []


def _reap() -> None:
    for process in list(_running):
        if process.poll() is not None:
            _running.remove(process)


def run_script(script_path: Path, terminal: str = DEFAULT_TERMINAL) -> bool:
    """Open a new detached terminal window running script_path, then drop
    into an interactive shell so the output stays visible afterward.
    Returns whether the terminal process was started successfully.

    Linux only: `terminal` defaults to x-terminal-emulator, the Debian/Ubuntu
    alternative for the system's configured default terminal. Per Debian
    Policy, every registered alternative must support `-e <program>
    <args...>` -- passed here as separate argv elements rather than one
    shell-parsed string, so behavior does not depend on the target terminal's
    own quoting rules.

    start_new_session=True detaches the terminal into its own session, so it
    survives the application quitting -- what QProcess.startDetached() used
    to provide before this module dropped its Qt dependency.
    """
    _reap()
    command = f"{shlex.quote(str(script_path))}; exec bash"
    try:
        process = subprocess.Popen(
            [terminal, "-e", "bash", "-c", command], start_new_session=True
        )
    except OSError:
        return False
    _running.append(process)
    return True
