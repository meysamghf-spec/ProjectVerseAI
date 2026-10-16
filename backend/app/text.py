"""Persian/Arabic text normalization for matching and number parsing."""

from __future__ import annotations

import re
import unicodedata

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "ٱ": "ا"})
_SEPARATORS = str.maketrans({"٬": ",", "٫": ".", "،": ",", "\u200c": " ", "\u200f": "", "\u200e": ""})
_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u0640]")  # harakat, superscript alef, tatweel
_SPACES = re.compile(r"\s+")


def normalize_digits(text: str) -> str:
    """Persian/Arabic-Indic digits and separators to ASCII, so regexes can read numbers."""

    return (text or "").translate(_DIGITS).translate(_SEPARATORS)


def normalize_for_search(text: str) -> str:
    """Case-fold and unify Persian/Arabic letter variants, digits, ZWNJ, and spacing."""

    value = unicodedata.normalize("NFC", text or "")
    value = normalize_digits(value).translate(_LETTERS)
    value = _DIACRITICS.sub("", value)
    return _SPACES.sub(" ", value).strip().casefold()
