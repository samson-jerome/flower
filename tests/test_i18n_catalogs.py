import re
from pathlib import Path
from flower import i18n

SRC = Path(__file__).resolve().parents[1] / "src" / "flower"

# Matches t("some.key"). The \b before t rules out setText(, format(, print(:
# in those the character before the t is a word character.
_CALL = re.compile(r"\bt\(\s*\"([^\"]+)\"")


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
