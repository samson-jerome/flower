from __future__ import annotations
import json
from importlib import resources

# Named in their own language: someone stuck in a language they cannot read
# has to be able to find their own in the list.
AVAILABLE_LANGUAGES: dict[str, str] = {"fr": "Français", "en": "English"}

_catalog: dict[str, str] = {}


def load_catalog(language: str) -> dict[str, str]:
    """Read locales/<language>.json and return it.

    Read through importlib.resources rather than a path relative to __file__,
    so resolution survives an installed wheel."""
    path = resources.files(__package__).joinpath(f"locales/{language}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def load(language: str) -> None:
    """Make `language` the active catalog.

    Called once by main(), before any widget is built: the language only
    changes on restart, so a module-level catalog is the whole mechanism."""
    global _catalog
    _catalog = load_catalog(language)


def t(key: str, **kwargs) -> str:
    """Resolve `key`, interpolating `kwargs` when any is given.

    A missing key returns itself: an untranslated `menu.file.open` on screen
    is ugly enough to be reported, where a silent fallback would hide the
    hole. The parity and consistency tests are the real safety net.

    str.format runs only when arguments are passed, so a text carrying
    literal braces does not raise."""
    text = _catalog.get(key, key)
    return text.format(**kwargs) if kwargs else text
