"""textstats - a tiny text analysis library."""

from .core import analyze, count_characters, count_lines, count_words, most_common_word

__all__ = [
    "analyze",
    "count_characters",
    "count_lines",
    "count_words",
    "most_common_word",
    "__version__",
]

__version__ = "1.0.0"
