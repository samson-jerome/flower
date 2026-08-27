import sys
from importlib.metadata import PackageNotFoundError

import pytest

from flower import version as version_module
from flower.app import main as main_module
from flower.version import UNKNOWN, get_version


def test_the_version_is_actually_resolvable():
    """The distribution name get_version() asks for must match pyproject's
    [project] name. If the two ever drift apart, get_version() returns
    UNKNOWN in silence and every version Flower reports becomes a lie --
    this test turns that silent failure into a loud one."""
    resolved = get_version()
    assert resolved != UNKNOWN
    assert resolved


def test_the_version_falls_back_when_the_package_is_not_installed(monkeypatch):
    """Flower run straight from a source tree (PYTHONPATH, no install) has no
    metadata to read. That must degrade to UNKNOWN, never raise: a missing
    version is not a reason to refuse to start."""
    def not_installed(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(version_module, "_metadata_version", not_installed)

    assert get_version() == UNKNOWN


def test_the_version_flag_prints_and_exits_without_building_a_qapplication(capsys, monkeypatch):
    """--version has to answer on a machine with no display, so it must be
    handled before Qt is touched at all. Building a QApplication here would
    fail on a headless box -- exactly where you most want to ask which
    version is installed."""
    def refuse(*args, **kwargs):
        raise AssertionError("--version must not build a QApplication")

    monkeypatch.setattr(sys, "argv", ["flower", "--version"])
    monkeypatch.setattr(main_module, "QApplication", refuse)

    with pytest.raises(SystemExit) as excinfo:
        main_module.main()

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"flower {get_version()}"
