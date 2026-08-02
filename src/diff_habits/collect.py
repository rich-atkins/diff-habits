"""Reading added lines out of a repository, one commit at a time.

Only added lines are examined. Deletions cannot introduce duplication or a swallowed
error, and including them would double-count a moved line as both.

Exclusion rules are reused from git-habits rather than reimplemented, so a path
excluded there is excluded here and the two tools' numbers stay comparable.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from git_habits.exclude import Excluder
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "diff-habits requires git-habits. Install it first:\n"
        "  pip install -e ../git-habits\n"
        "or  pip install git-habits"
    ) from e

_DIFF_FORMAT = "COMMIT%x09%H%x09%ae%x09%aI"


@dataclass
class AddedChunk:
    sha: str
    author_email: str
    authored_at: datetime
    path: str
    lines: list[str]


class DiffCollectError(RuntimeError):
    pass


def collect(
    repo: str | Path,
    excluder: Excluder,
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
    all_refs: bool = False,
) -> list[AddedChunk]:
    """Walk history and yield the added lines of every non-excluded file."""
    cmd = ["git", "-C", str(repo), "log", "--no-merges", "-p", "-U0",
           "--no-color", f"--format={_DIFF_FORMAT}"]
    if all_refs:
        cmd.insert(4, "--all")
    if author:
        cmd += ["--author", author, "--regexp-ignore-case"]
    if since:
        cmd += [f"--since={since}"]
    if until:
        cmd += [f"--until={until}"]

    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise DiffCollectError(f"git log failed: {proc.stderr.strip()}")

    out: list[AddedChunk] = []
    sha = email = ""
    when: datetime | None = None
    path: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, path
        if path and buf and when is not None:
            if excluder.category_for(path) is None:
                out.append(AddedChunk(sha, email, when, path, list(buf)))
        buf = []

    for line in proc.stdout.splitlines():
        if line.startswith("COMMIT\t"):
            flush()
            path = None
            parts = line.split("\t")
            if len(parts) >= 4:
                sha, email = parts[1], parts[2]
                when = datetime.fromisoformat(parts[3])
            continue
        if line.startswith("+++ b/"):
            flush()
            path = line[6:].strip()
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        # -U0 means every '+' line is a genuine addition, not context.
        if line.startswith("+") and not line.startswith("+++"):
            buf.append(line[1:])

    flush()
    if not out:
        raise DiffCollectError(
            "no added lines found. Check the author filter and date range, and note "
            "that an over-narrow --author matches nothing while exiting 0."
        )
    return out
