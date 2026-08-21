from pathlib import Path
import pytest
from PySide6.QtCore import QSettings
from flower.app.prefs import recent


@pytest.fixture(autouse=True)
def clean_settings(qapp, tmp_path, monkeypatch):
    """Keep QSettings out of the developer's real configuration."""
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    QSettings().clear()
    yield
    QSettings().clear()


def test_load_recent_starts_empty():
    assert recent.load_recent() == []


def test_add_recent_puts_the_newest_first(tmp_path):
    recent.add_recent(tmp_path / "a.flow")
    recent.add_recent(tmp_path / "b.flow")

    assert [Path(p).name for p in recent.load_recent()] == ["b.flow", "a.flow"]


def test_add_recent_moves_a_known_path_back_to_the_top(tmp_path):
    recent.add_recent(tmp_path / "a.flow")
    recent.add_recent(tmp_path / "b.flow")
    recent.add_recent(tmp_path / "a.flow")

    names = [Path(p).name for p in recent.load_recent()]
    assert names == ["a.flow", "b.flow"]


def test_add_recent_caps_the_list(tmp_path):
    for i in range(recent.MAX_RECENT + 5):
        recent.add_recent(tmp_path / f"f{i}.flow")

    assert len(recent.load_recent()) == recent.MAX_RECENT


def test_remove_recent(tmp_path):
    recent.add_recent(tmp_path / "a.flow")
    recent.add_recent(tmp_path / "b.flow")

    recent.remove_recent(tmp_path / "a.flow")

    assert [Path(p).name for p in recent.load_recent()] == ["b.flow"]


def test_clear_recent(tmp_path):
    recent.add_recent(tmp_path / "a.flow")

    recent.clear_recent()

    assert recent.load_recent() == []


def test_load_recent_tolerates_a_single_string(tmp_path):
    # QSettings reads a one-element list back as a bare string.
    QSettings().setValue("recentFiles", str(tmp_path / "a.flow"))
    assert [Path(p).name for p in recent.load_recent()] == ["a.flow"]
