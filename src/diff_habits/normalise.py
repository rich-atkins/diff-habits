"""Deciding what counts as a meaningful line.

Duplication measured on raw text is close to useless: every file has closing braces,
blank lines and imports, and counting those as repetition produces a large number
that means nothing. GitClear's published definition talks about *meaningful* lines,
so this module is where that judgement lives, in one place, visible and testable.

Normalisation is deliberately conservative. It strips whitespace and nothing else.
Aggressive normalisation (renaming identifiers, dropping punctuation) inflates
duplication counts and makes results incomparable with anyone else's.
"""
from __future__ import annotations

import re

# Lines that are structurally necessary but carry no logic. Repeating these is not
# duplication in any sense a reader cares about.
_TRIVIAL = re.compile(
    r"^[\s\{\}\(\)\[\];,]*$"          # braces, brackets, semicolons, blank
    r"|^(?:end|fi|done|esac)$"         # block terminators
)

_COMMENT_PREFIXES = ("//", "#", "*", "/*", "*/", "--", "<!--", '"""', "'''")

# Import and using statements repeat across every file in a codebase by design.
_IMPORTISH = re.compile(
    r"^\s*(?:import|from|using|require|include|package|use|#include)\b"
)

MIN_MEANINGFUL_CHARS = 3


def is_meaningful(line: str) -> bool:
    """True when a line carries enough content for repetition to mean something."""
    s = line.strip()
    if len(s) < MIN_MEANINGFUL_CHARS:
        return False
    if _TRIVIAL.match(s):
        return False
    if s.startswith(_COMMENT_PREFIXES):
        return False
    if _IMPORTISH.match(s):
        return False
    return True


def normalise(line: str) -> str:
    """Collapse insignificant whitespace so reformatting is not read as new code.

    Indentation and internal spacing vary with formatters; the tokens do not.
    """
    return re.sub(r"\s+", " ", line.strip())


def meaningful_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return (original_index, normalised_text) for lines worth comparing."""
    return [(i, normalise(l)) for i, l in enumerate(lines) if is_meaningful(l)]
