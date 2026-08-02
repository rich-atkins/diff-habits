"""Tests for normalisation, duplication and masking detection."""
from __future__ import annotations

from diff_habits.duplication import DuplicationDetector
from diff_habits.masking import MaskingDetector
from diff_habits.normalise import is_meaningful, meaningful_lines, normalise


# --- what counts as meaningful ---------------------------------------------------

def test_braces_and_blanks_are_not_meaningful():
    for line in ["}", "  {", "", "   ", ");", "};"]:
        assert not is_meaningful(line), line


def test_comments_are_not_meaningful():
    for line in ["// nope", "# nope", "* doc", "-- sql comment"]:
        assert not is_meaningful(line)


def test_imports_are_not_meaningful():
    """Imports repeat across every file by design; counting them inflates duplication."""
    for line in ["import os", "from a import b", "using System;", "#include <stdio.h>"]:
        assert not is_meaningful(line)


def test_real_code_is_meaningful():
    assert is_meaningful("const total = items.reduce((a, b) => a + b, 0)")


def test_normalise_collapses_whitespace_so_reformatting_is_not_new_code():
    assert normalise("  const   a =  1  ") == normalise("const a = 1")


def test_meaningful_lines_preserves_original_indices():
    idx = [i for i, _ in meaningful_lines(["}", "let a = 1", "", "let b = 2"])]
    assert idx == [1, 3]


# --- duplication -----------------------------------------------------------------

def _block(n: int, prefix: str = "x") -> list[str]:
    return [f"const {prefix}{i} = compute({i});" for i in range(n)]


def test_identical_five_line_block_is_duplication():
    d = DuplicationDetector()
    d.add(_block(5))
    d.add(_block(5))
    assert d.result.blocks == 1
    assert d.result.duplicated_lines == 5


def test_four_lines_is_below_threshold():
    d = DuplicationDetector()
    d.add(_block(4))
    d.add(_block(4))
    assert d.result.blocks == 0


def test_distinct_code_is_not_duplication():
    d = DuplicationDetector()
    d.add(_block(5, "a"))
    d.add(_block(5, "b"))
    assert d.result.duplicated_lines == 0


def test_longer_repeat_counts_once_not_as_overlapping_windows():
    """A 12-line repeat is one block of 12, not eight overlapping 5-line hits."""
    d = DuplicationDetector()
    d.add(_block(12))
    d.add(_block(12))
    assert d.result.blocks == 1
    assert d.result.duplicated_lines == 12


def test_reformatted_copy_still_counts():
    d = DuplicationDetector()
    d.add(_block(5))
    d.add(["   " + l + "  " for l in _block(5)])
    assert d.result.duplicated_lines == 5


def test_rate_normalised_per_million_added_lines():
    d = DuplicationDetector()
    d.add(_block(5))
    d.add(_block(5))
    assert d.result.changed_lines_seen == 10
    assert d.result.per_million_changed == 500_000.0


# --- error masking ---------------------------------------------------------------

def test_empty_catch_is_hard_masking():
    m = MaskingDetector()
    m.add("a.ts", ["try { go() } catch (e) {}"])
    assert m.result.hard_hits == 1


def test_except_pass_is_hard_masking():
    m = MaskingDetector()
    m.add("a.py", ["except ValueError:", "    pass"])
    assert m.result.by_pattern.get("except_pass_py", 0) == 0  # split across lines
    m2 = MaskingDetector()
    m2.add("a.py", ["except ValueError: pass"])
    assert m2.result.hard_hits == 1


def test_optional_chaining_is_soft_not_hard():
    """Legitimate often enough that counting it as masking would mislead."""
    m = MaskingDetector()
    m.add("a.ts", ["const n = user?.profile?.name"])
    assert m.result.soft_hits >= 1
    assert m.result.hard_hits == 0


def test_ts_suppression_is_hard():
    m = MaskingDetector()
    m.add("a.ts", ["// @ts-ignore", "doThing()"])
    assert m.result.hard_hits == 1


def test_language_scoping_prevents_cross_language_false_positives():
    m = MaskingDetector()
    m.add("a.py", ["const x = user?.name"])  # not a Python construct
    assert m.result.soft_hits == 0


def test_rate_is_per_thousand_added_lines():
    m = MaskingDetector()
    m.add("a.ts", ["// @ts-ignore"] + ["const a = 1"] * 999)
    assert m.result.lines_seen == 1000
    assert m.result.hard_per_kloc == 1.0
