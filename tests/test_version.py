from importlib.metadata import PackageNotFoundError
from flower import version as version_module
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
