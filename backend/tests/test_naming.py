"""Алиас из названия, проверка названия и кода страны."""
import pytest

from app.domain.errors import ValidationError
from app.domain.naming import MAX_ALIAS_LENGTH, make_alias, normalize_geo, normalize_name


@pytest.mark.parametrize("name,alias", [
    ("Тест кампания", "test-kampaniya"),
    ("Campaign 2", "campaign-2"),
    ("  Лето!!!  2026  ", "leto-2026"),
    ("Щука & Ёж", "schuka-ezh"),
    ("a--b__c", "a-b-c"),
])
def test_alias_is_transliterated_and_slugified(name, alias):
    assert make_alias(name) == alias


def test_alias_is_limited_in_length_and_has_no_trailing_dash():
    alias = make_alias("слово " * 40)
    assert len(alias) <= MAX_ALIAS_LENGTH and not alias.endswith("-")


def test_name_must_not_be_empty_or_symbols_only():
    for bad in ("", "   ", "!!!", None):
        with pytest.raises(ValidationError) as info:
            normalize_name(bad)
        assert info.value.field == "name"


def test_name_is_trimmed_and_length_limited():
    assert normalize_name("  Кампания  ") == "Кампания"
    with pytest.raises(ValidationError):
        normalize_name("а" * 256)


@pytest.mark.parametrize("code,expected", [("au", "AU"), ("Ro", "RO"), (" cl ", "CL")])
def test_geo_is_uppercased(code, expected):
    assert normalize_geo(code) == expected


@pytest.mark.parametrize("code", ["", "A", "AUS", "1A", "А1", "ру", None])
def test_geo_rejects_wrong_codes(code):
    with pytest.raises(ValidationError) as info:
        normalize_geo(code)
    assert info.value.field == "geo"
