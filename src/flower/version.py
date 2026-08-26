from __future__ import annotations
from importlib.metadata import PackageNotFoundError, version as _metadata_version

UNKNOWN = "inconnue"


def get_version() -> str:
    """The installed distribution's version, or UNKNOWN when Flower runs from
    a source tree that was never installed (PYTHONPATH, a checkout run with
    `python -m`).

    Reads the *installed* metadata, not the repository: hatch-vcs freezes the
    version at install time, so a freshly created tag only shows up here once
    the package is reinstalled (`uv sync --reinstall-package flower`).
    Deriving it from `git describe` at runtime would make a graphical
    application depend on git being installed, and would report a version no
    build ever produced.
    """
    try:
        return _metadata_version("flower")
    except PackageNotFoundError:
        return UNKNOWN
