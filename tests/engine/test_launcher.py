import shlex
from pathlib import Path
from PySide6.QtCore import QProcess
from flower.engine.execution.launcher import launch_in_terminal


def test_launch_in_terminal_calls_startDetached_with_expected_args(monkeypatch):
    calls = []
    monkeypatch.setattr(
        QProcess, "startDetached",
        staticmethod(lambda program, args: calls.append((program, args)) or True),
    )
    script_path = Path("/tmp/demo_20260702-143022.sh")

    result = launch_in_terminal(script_path)

    assert len(calls) == 1
    program, args = calls[0]
    assert program == "x-terminal-emulator"
    assert args == ["-e", "bash", "-c", f"{shlex.quote(str(script_path))}; exec bash"]
    assert result is True


def test_launch_in_terminal_returns_false_on_failure(monkeypatch):
    monkeypatch.setattr(QProcess, "startDetached", staticmethod(lambda program, args: False))
    script_path = Path("/tmp/demo_20260702-143022.sh")

    assert launch_in_terminal(script_path) is False


def test_launch_in_terminal_quotes_path_with_spaces(monkeypatch):
    calls = []
    monkeypatch.setattr(
        QProcess, "startDetached",
        staticmethod(lambda program, args: calls.append((program, args)) or True),
    )
    script_path = Path("/tmp/my flow_20260702-143022.sh")

    launch_in_terminal(script_path)

    _, args = calls[0]
    assert args[-1] == f"{shlex.quote(str(script_path))}; exec bash"
    assert "my flow" in args[-1]
