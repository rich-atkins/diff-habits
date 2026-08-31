"""Evidence-sufficiency guards (v0.2): thin is not evidence, empty is not a report.

Masking events are rare (roughly 0.2-4 per 1k added lines in the wild), so a
per-1k rate computed over a couple of hundred lines is noise. Below the floor
the rate is refused, not reported; an empty compare window refuses the whole
comparison at exit 1 and NAMES the empty window (v0.1 aborted with a generic
error before even collecting the second window).
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from conftest import clean_py_lines, make_repo

from diff_habits.cli import main

SPLIT = "2026-04-13"


def _thin_repo(tmp_path):
    # 2 commits, 120 added lines total: far below the 500-line floor.
    return make_repo(tmp_path, [
        {"date": "2026-03-01T10:00:00",
         "files": {"src/a.py": clean_py_lines(60, "t0")}, "message": "one"},
        {"date": "2026-03-05T10:00:00",
         "files": {"src/b.py": clean_py_lines(60, "t1")}, "message": "two"},
    ])


def test_scan_renders_insufficient_not_numbers(tmp_path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["scan", "--repo", str(_thin_repo(tmp_path))])
    out = buf.getvalue()
    assert rc == 0
    assert "insufficient (n=120 added lines, need >=500)" in out
    assert "per 1k added)" not in out  # no rate presented as a number
    assert "added lines          120" in out  # raw counts stay visible


def test_scan_json_carries_insufficiency(tmp_path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["scan", "--repo", str(_thin_repo(tmp_path)), "--json"])
    d = json.loads(buf.getvalue())
    assert "masking_hard_per_kloc" in d["insufficient"]
    assert isinstance(d["masking_hard_per_kloc"], float)  # JSON stays numeric


def test_compare_refuses_and_names_the_empty_window(tmp_path, capsys):
    rc = main(["compare", "--repo", str(_thin_repo(tmp_path)), "--split", "2026-01-01"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "comparison refused" in captured.err
    assert "'before'" in captured.err  # the empty side is NAMED


def test_floor_is_overridable(tmp_path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["scan", "--repo", str(_thin_repo(tmp_path)),
                   "--min-evidence-lines", "50"])
    assert rc == 0
    assert "insufficient" not in buf.getvalue()
