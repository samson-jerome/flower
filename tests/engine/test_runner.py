import shlex
import subprocess
from pathlib import Path
from flower.engine.execution import runner


class _FakePopen:
    """Stand-in for subprocess.Popen recording its argv and poll() calls."""

    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.polls = 0

    def poll(self):
        self.polls += 1
        return 0


def _spy(monkeypatch, created):
    def fake_popen(argv, **kwargs):
        process = _FakePopen(argv, **kwargs)
        created.append(process)
        return process
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner, "_running", [])


def test_run_script_spawns_the_terminal_with_expected_argv(monkeypatch):
    created = []
    _spy(monkeypatch, created)
    script_path = Path("/tmp/demo_20260702-143022.sh")

    assert runner.run_script(script_path) is True

    assert len(created) == 1
    assert created[0].argv == [
        "x-terminal-emulator", "-e", "bash", "-c",
        f"{shlex.quote(str(script_path))}; exec bash",
    ]
    assert created[0].kwargs["start_new_session"] is True


def test_run_script_quotes_a_path_with_spaces(monkeypatch):
    created = []
    _spy(monkeypatch, created)
    script_path = Path("/tmp/my flow_20260702-143022.sh")

    runner.run_script(script_path)

    command = created[0].argv[-1]
    assert command == f"{shlex.quote(str(script_path))}; exec bash"
    assert "my flow" in command


def test_run_script_honours_a_custom_terminal(monkeypatch):
    created = []
    _spy(monkeypatch, created)

    runner.run_script(Path("/tmp/demo.sh"), terminal="kitty")

    assert created[0].argv[0] == "kitty"


def test_run_script_returns_false_when_the_terminal_is_missing(monkeypatch):
    def boom(argv, **kwargs):
        raise FileNotFoundError(argv[0])
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(runner, "_running", [])

    assert runner.run_script(Path("/tmp/demo.sh")) is False


def test_run_script_reaps_previous_launches(monkeypatch):
    created = []
    _spy(monkeypatch, created)

    runner.run_script(Path("/tmp/one.sh"))
    runner.run_script(Path("/tmp/two.sh"))

    # The first launch is polled by the second, so a finished terminal does
    # not linger as a zombie for the lifetime of the application.
    assert created[0].polls == 1


def test_open_terminal_spawns_the_terminal_in_the_directory(monkeypatch):
    created = []
    _spy(monkeypatch, created)

    assert runner.open_terminal(Path("/tmp/flows")) is True

    # No -e: this opens an interactive shell, not a command.
    assert created[0].argv == ["x-terminal-emulator"]
    assert created[0].kwargs["cwd"] == "/tmp/flows"
    assert created[0].kwargs["start_new_session"] is True


def test_open_terminal_honours_a_custom_terminal(monkeypatch):
    created = []
    _spy(monkeypatch, created)

    runner.open_terminal(Path("/tmp/flows"), terminal="kitty")

    assert created[0].argv == ["kitty"]


def test_open_terminal_returns_false_when_the_terminal_is_missing(monkeypatch):
    def boom(argv, **kwargs):
        raise FileNotFoundError(argv[0])
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(runner, "_running", [])

    assert runner.open_terminal(Path("/tmp/flows")) is False


def test_open_editor_passes_the_path_to_the_editor(monkeypatch):
    created = []
    _spy(monkeypatch, created)

    assert runner.open_editor(Path("/tmp/flows")) is True

    assert created[0].argv == ["code", "/tmp/flows"]
    assert created[0].kwargs["start_new_session"] is True


def test_open_editor_splits_a_command_with_arguments(monkeypatch):
    """An editor is commonly configured with arguments, unlike a terminal."""
    created = []
    _spy(monkeypatch, created)

    runner.open_editor(Path("/tmp/flows"), editor="flatpak run com.visualstudio.code -n")

    assert created[0].argv == [
        "flatpak", "run", "com.visualstudio.code", "-n", "/tmp/flows",
    ]


def test_open_editor_refuses_a_blank_command(monkeypatch):
    """Without this guard the split would yield an empty argv and the path
    itself would be executed as the program."""
    created = []
    _spy(monkeypatch, created)

    assert runner.open_editor(Path("/tmp/flows"), editor="   ") is False
    assert created == []


def test_open_editor_returns_false_when_the_editor_is_missing(monkeypatch):
    def boom(argv, **kwargs):
        raise FileNotFoundError(argv[0])
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(runner, "_running", [])

    assert runner.open_editor(Path("/tmp/flows")) is False


def test_open_editor_refuses_a_malformed_command(monkeypatch):
    """An unbalanced quote in the preference is a configuration mistake, not an
    exception for the caller to handle: shlex.split would raise ValueError."""
    created = []
    _spy(monkeypatch, created)

    assert runner.open_editor(Path("/tmp/flows"), editor='code "') is False
    assert created == []

