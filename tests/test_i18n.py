import pytest
from flower import i18n


@pytest.fixture(autouse=True)
def fake_catalog(monkeypatch):
    """Isolate t() from the shipped catalogs: this module tests resolution,
    not the wording."""
    monkeypatch.setattr(i18n, "_catalog", {
        "greeting":       "Bonjour",
        "greeting.named": "Bonjour {name}",
        "literal.braces": "Un dict vide s'écrit {}",
    })


def test_known_key_resolves_to_its_text():
    assert i18n.t("greeting") == "Bonjour"


def test_unknown_key_is_returned_as_is():
    assert i18n.t("menu.file.nope") == "menu.file.nope"


def test_named_arguments_are_interpolated():
    assert i18n.t("greeting.named", name="Ada") == "Bonjour Ada"


def test_braces_survive_when_no_argument_is_given():
    # str.format would raise on a bare {} -- t() must not call it for nothing.
    assert i18n.t("literal.braces") == "Un dict vide s'écrit {}"


def test_load_catalog_reads_a_shipped_file():
    for language in i18n.AVAILABLE_LANGUAGES:
        catalog = i18n.load_catalog(language)
        assert isinstance(catalog, dict)
        assert all(isinstance(k, str) and isinstance(v, str)
                   for k, v in catalog.items())


def test_load_catalog_rejects_an_unshipped_language():
    with pytest.raises(FileNotFoundError):
        i18n.load_catalog("klingon")


def test_available_languages_are_named_in_their_own_language():
    assert i18n.AVAILABLE_LANGUAGES == {"fr": "Français", "en": "English"}


def test_load_replaces_the_active_catalog():
    i18n.load("fr")
    assert i18n.t("greeting") == "greeting"
