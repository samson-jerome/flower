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
