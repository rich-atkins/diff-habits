"""Sabotage self-test: prove the tool CATCHES what it claims to measure.

Two real repositories per run:
  * PLANTED — hard-masking density jumps sharply after 2026-04-13 (silent
    exception swallows start appearing in added code).
  * CONTROL — same clean regime throughout.
`compare` must flag the planted shift and must NOT flag the control. Both
directions matter: a detector that always fires is as broken as one that never
does.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from conftest import clean_py_lines, make_repo, masked_py_lines

from diff_habits.cli import main

SPLIT = "2026-04-13"


def _compare_json(repo) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["compare", "--repo", str(repo), "--split", SPLIT, "--json"])
    assert rc == 0, buf.getvalue()
    return json.loads(buf.getvalue())


def _planted(tmp_path):
    commits = []
    # Before: 6 clean commits, 120 added lines each (720 total, above the floor).
    for i in range(6):
        commits.append({
            "date": f"2026-0{1 + i // 3}-{5 + (i % 3) * 8:02d}T10:00:00",
            "files": {f"src/mod_{i % 2}.py": clean_py_lines(120, f"b{i}", start=i * 500)},
            "message": f"feat: clean change {i}",
            "append": True,
        })
    # After: 6 commits, same volume, but ~15 silent swallows per commit.
    for i in range(6):
        commits.append({
            "date": f"2026-06-{4 + i * 4:02d}T10:00:00",
            "files": {f"src/mod_{i % 2}.py": masked_py_lines(60, 15, f"a{i}", start=5000 + i * 500)},
            "message": f"feat: rushed change {i}",
            "append": True,
        })
    return make_repo(tmp_path, commits)


def _control(tmp_path):
    commits = []
    for i in range(12):
        commits.append({
            "date": f"2026-{1 + i // 2:02d}-{4 + (i % 2) * 12:02d}T10:00:00",
            "files": {f"src/mod_{i % 2}.py": clean_py_lines(120, f"s{i}", start=i * 500)},
            "message": f"feat: steady change {i}",
            "append": True,
        })
    return make_repo(tmp_path, commits)


def test_planted_masking_shift_is_flagged(tmp_path):
    d = _compare_json(_planted(tmp_path))
    before, after = d["before"], d["after"]
    assert before["masking_hard_per_kloc"] == 0.0
    assert after["masking_hard"] >= 80  # ~15 swallows x 6 commits
    assert after["masking_hard_per_kloc"] > 50
    # The evidence floor must not be hiding either side.
    assert d["insufficient"]["before"] == {}
    assert d["insufficient"]["after"] == {}


def test_control_repo_stays_quiet(tmp_path):
    d = _compare_json(_control(tmp_path))
    assert d["before"]["masking_hard"] == 0
    assert d["after"]["masking_hard"] == 0
    assert d["insufficient"]["before"] == {}
    assert d["insufficient"]["after"] == {}


def test_boundary_commit_counted_once(tmp_path):
    """A commit exactly at the split instant lands in ONE window (v0.1 counted
    it in both: git's --since and --until are both inclusive)."""
    commits = [
        {"date": "2026-03-01T10:00:00",
         "files": {"src/a.py": clean_py_lines(60, "pre")}, "message": "pre"},
        {"date": f"{SPLIT}T00:00:00",
         "files": {"src/b.py": clean_py_lines(70, "edge")}, "message": "edge"},
        {"date": "2026-05-01T10:00:00",
         "files": {"src/c.py": clean_py_lines(80, "post")}, "message": "post"},
    ]
    repo = make_repo(tmp_path, commits)
    d = _compare_json(repo)
    total = d["before"]["added_lines"] + d["after"]["added_lines"]
    assert total == 60 + 70 + 80, (d["before"]["added_lines"], d["after"]["added_lines"])
    assert d["after"]["added_lines"] == 70 + 80  # boundary commit -> after only
