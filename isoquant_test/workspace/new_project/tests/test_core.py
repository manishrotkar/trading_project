"""Tests for the textstats package."""

from textstats import (
    analyze,
    count_characters,
    count_lines,
    count_words,
    most_common_word,
)


def test_count_lines() -> None:
    assert count_lines("") == 0
    assert count_lines("hello") == 1
    assert count_lines("one\ntwo\nthree") == 3


def test_count_words() -> None:
    assert count_words("") == 0
    assert count_words("hello world") == 2
    assert count_words("  spaces   everywhere ") == 2
    assert count_words("it's v2.0") == 3  # it's, v2, 0


def test_count_characters() -> None:
    text = "a b\t"
    assert count_characters(text) == 4
    assert count_characters(text, include_spaces=False) == 2


def test_count_characters_hello_world() -> None:
    text = "Hello world\nHello again"
    # 23 total chars, 3 whitespace chars (1 newline + 1 + 1 space)
    assert count_characters(text) == 23
    assert count_characters(text, include_spaces=False) == 20


def test_most_common_word() -> None:
    text = "cat dog cat bird dog cat"
    assert most_common_word(text, n=1) == [("cat", 3)]
    assert most_common_word(text, n=2)[1] == ("dog", 2)


def test_analyze_summary() -> None:
    stats = analyze("Hello world\nHello again")
    assert stats["lines"] == 2
    assert stats["words"] == 4
    assert stats["characters"] == 23
    assert stats["characters_no_spaces"] == 20
    assert stats["top_word"] == "hello"
    assert stats["top_word_count"] == 2


def test_analyze_empty() -> None:
    stats = analyze("")
    assert stats["lines"] == 0
    assert stats["words"] == 0
    assert stats["top_word"] is None
    assert stats["top_word_count"] == 0
