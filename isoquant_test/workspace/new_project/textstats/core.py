"""Core text analysis functions."""

from __future__ import annotations

import re
from collections import Counter


def count_lines(text: str) -> int:
    """Return the number of lines in *text*."""
    if not text:
        return 0
    return len(text.splitlines())


def count_words(text: str) -> int:
    """Return the number of words (runs of letters/digits) in *text*."""
    return len(re.findall(r"[A-Za-z0-9']+", text))


def count_characters(text: str, *, include_spaces: bool = True) -> int:
    """Return the number of characters in *text*.

    When ``include_spaces`` is False, whitespace is ignored.
    """
    if include_spaces:
        return len(text)
    return sum(1 for ch in text if not ch.isspace())


def most_common_word(text: str, n: int = 5) -> list[tuple[str, int]]:
    """Return the *n* most common words with their counts.

    Matching is case-insensitive.
    """
    words = re.findall(r"[a-z0-9']+", text.lower())
    return Counter(words).most_common(n)


def analyze(text: str) -> dict[str, object]:
    """Return a summary dictionary with basic statistics for *text*."""
    lines = count_lines(text)
    words = count_words(text)
    chars = count_characters(text)
    chars_no_ws = count_characters(text, include_spaces=False)
    top = most_common_word(text, n=1)
    return {
        "lines": lines,
        "words": words,
        "characters": chars,
        "characters_no_spaces": chars_no_ws,
        "top_word": top[0][0] if top else None,
        "top_word_count": top[0][1] if top else 0,
    }
