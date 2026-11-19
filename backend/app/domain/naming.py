"""Правила названий для создания кампании: алиас из названия и код страны."""
import re

from app.domain.errors import ValidationError

MAX_NAME_LENGTH = 255  # максимальная длина названия кампании
MAX_ALIAS_LENGTH = 60  # максимальная длина алиаса

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ы": "y", "э": "e",
    "ю": "yu", "я": "ya", "ъ": "", "ь": "",
}
_GEO_PATTERN = re.compile(r"^[A-Za-z]{2}$")


def make_alias(name: str) -> str:
    """Строит алиас из названия: транслитерация, строчные латинские буквы и цифры, слова через дефис."""
    # переводим кириллицу в латиницу
    transliterated = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    # всё кроме латиницы и цифр становится разделителем
    alias = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    return alias[:MAX_ALIAS_LENGTH].strip("-")


def normalize_name(name: str) -> str:
    """Проверяет и очищает название кампании."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValidationError("name", "Введите название кампании.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationError("name", f"Название длиннее {MAX_NAME_LENGTH} символов.")
    if not make_alias(cleaned):
        raise ValidationError("name", "В названии должны быть буквы или цифры: из него строится алиас.")
    return cleaned


def normalize_geo(code: str) -> str:
    """Проверяет код страны (две латинские буквы) и приводит его к верхнему регистру."""
    cleaned = (code or "").strip()
    if not _GEO_PATTERN.match(cleaned):
        raise ValidationError("geo", "Код страны — две латинские буквы, например AU.")
    return cleaned.upper()
