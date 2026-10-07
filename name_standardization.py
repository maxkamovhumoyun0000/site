"""Shared, deterministic standards for user first and last names.

New records are deliberately strict: only Latin-script names are accepted and
they are stored in uppercase.  Legacy records may contain Cyrillic text, so
the audit tool uses the Uzbek/Russian transliteration table below before
flagging anything that still needs a human review.
"""

from __future__ import annotations

import re
import unicodedata


_APOSTROPHES = str.maketrans({
    "ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'", "´": "'", "ʹ": "'",
})

# This table handles both Uzbek-specific Cyrillic letters and the commonly
# encountered Russian ones. It is intentionally character-by-character so an
# audit always has one reproducible result rather than a guessed personal name.
_CYRILLIC_TO_LATIN = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "YO",
    "Ж": "J", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "H", "Ц": "TS", "Ч": "CH", "Ш": "SH", "Щ": "SHCH",
    "Ъ": "", "Ы": "I", "Ь": "", "Э": "E", "Ю": "YU", "Я": "YA",
    "Ў": "O'", "Қ": "Q", "Ғ": "G'", "Ҳ": "H", "І": "I", "Ї": "YI", "Є": "YE",
}
_CYRILLIC_TO_LATIN.update({key.lower(): value.lower() for key, value in list(_CYRILLIC_TO_LATIN.items())})
_CYRILLIC_RE = re.compile(r"[\u0400-\u052F]")
_SPACE_RE = re.compile(r"\s+")


def has_cyrillic(value: str) -> bool:
    return bool(_CYRILLIC_RE.search(str(value or "")))


def _is_latin_letter(char: str) -> bool:
    if not char.isalpha():
        return False
    return "LATIN" in unicodedata.name(char, "")


def normalize_apostrophes(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).translate(_APOSTROPHES)


def transliterate_cyrillic(value: str) -> str:
    return "".join(_CYRILLIC_TO_LATIN.get(char, char) for char in normalize_apostrophes(value))


def _clean_spacing(value: str) -> str:
    return _SPACE_RE.sub(" ", value).strip()


def is_latin_name(value: str) -> bool:
    candidate = _clean_spacing(normalize_apostrophes(value))
    if not candidate or has_cyrillic(candidate):
        return False
    letter_count = 0
    for char in candidate:
        if _is_latin_letter(char):
            letter_count += 1
            continue
        if char in {" ", "'", "-"}:
            continue
        return False
    return letter_count > 0


def normalize_new_latin_name(value: str, field_name: str = "name") -> str:
    """Validate a newly entered name and return its canonical stored form."""
    candidate = _clean_spacing(normalize_apostrophes(value))
    if not candidate:
        raise ValueError(f"{field_name} is required")
    if has_cyrillic(candidate):
        raise ValueError(f"{field_name} must use the Latin alphabet; Cyrillic is not allowed")
    if not is_latin_name(candidate):
        raise ValueError(f"{field_name} must use Latin letters, spaces, apostrophes, or hyphens only")
    return candidate.upper()


def standardize_legacy_name(value: str) -> str:
    """Canonical form for audit/backfill; does not silently invent spellings."""
    return _clean_spacing(transliterate_cyrillic(value)).upper()


def name_search_terms(value: str) -> list[str]:
    """Return exact and X/H spelling alternatives for forgiving name search."""
    base = standardize_legacy_name(value)
    if not base:
        return []
    terms = {base}
    if "X" in base:
        terms.add(base.replace("X", "H"))
    if "H" in base:
        terms.add(base.replace("H", "X"))
    return sorted(term for term in terms if term)


def potential_duplicate_key(first_name: str, last_name: str) -> str:
    """Conservative similarity key used only to flag, never auto-merge users."""
    def compact(value: str) -> str:
        canonical = standardize_legacy_name(value)
        canonical = canonical.replace("X", "H")
        return "".join(char for char in canonical if _is_latin_letter(char))

    return f"{compact(first_name)}|{compact(last_name)}"
