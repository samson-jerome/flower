import re
from pathlib import Path
from flower import i18n

SRC = Path(__file__).resolve().parents[1] / "src" / "flower"

# Matches t("some.key"). The \b before t rules out setText(, format(, print(:
# in those the character before the t is a word character.
_CALL = re.compile(r"\bt\(\s*\"([^\"]+)\"")
_FIELD = re.compile(r"\{(\w+)\}")


def used_keys() -> set[str]:
    return {
        match.group(1)
        for path in sorted(SRC.rglob("*.py"))
        for match in _CALL.finditer(path.read_text(encoding="utf-8"))
    }


def test_both_catalogs_declare_the_same_keys():
    missing_in_en = set(i18n.load_catalog("fr")) - set(i18n.load_catalog("en"))
    missing_in_fr = set(i18n.load_catalog("en")) - set(i18n.load_catalog("fr"))
    assert missing_in_en == set()
    assert missing_in_fr == set()


def test_every_key_used_in_the_sources_exists_in_the_catalog():
    assert used_keys() - set(i18n.load_catalog("fr")) == set()


def test_the_catalog_carries_no_dead_key():
    assert set(i18n.load_catalog("fr")) - used_keys() == set()


def test_both_catalogs_interpolate_the_same_fields():
    """A placeholder renamed in one language only would raise KeyError at
    the call site, in whichever language nobody happened to run."""
    fr, en = i18n.load_catalog("fr"), i18n.load_catalog("en")
    for key in fr:
        assert set(_FIELD.findall(fr[key])) == set(_FIELD.findall(en[key])), key


def test_every_value_formats():
    """An unbalanced brace raises ValueError the moment the value is used."""
    for language in i18n.AVAILABLE_LANGUAGES:
        for key, value in i18n.load_catalog(language).items():
            value.format(**{field: "x" for field in _FIELD.findall(value)})
