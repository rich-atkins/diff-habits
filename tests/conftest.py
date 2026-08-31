"""Shared fixture: build real, deterministic git repositories for CLI-level tests.

The unit tests feed the detectors directly; these helpers exist for the sabotage
self-tests, which must exercise the WHOLE pipeline (git log -p -> collect ->
detectors -> CLI rendering) against an actual repository, because that is the path
a user runs. Everything is pinned so runs are reproducible.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, env_dates: str | None = None) -> None:
    env = {
        "GIT_AUTHOR_NAME": "Dev Example",
        "GIT_AUTHOR_EMAIL": "dev@example.com",
        "GIT_COMMITTER_NAME": "Dev Example",
        "GIT_COMMITTER_EMAIL": "dev@example.com",
        "HOME": str(repo),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if env_dates:
        env["GIT_AUTHOR_DATE"] = env_dates
        env["GIT_COMMITTER_DATE"] = env_dates
    subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                   capture_output=True, text=True)


def make_repo(root: Path, commits: list[dict]) -> Path:
    """Build a repo from a commit spec list.

    Each spec: {"date": "2026-01-05T10:00:00", "files": {path: [lines]},
                "message": str, "append": bool}
    """
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    for spec in commits:
        for path, lines in spec["files"].items():
            f = repo / path
            f.parent.mkdir(parents=True, exist_ok=True)
            text = "\n".join(lines) + "\n"
            if spec.get("append") and f.exists():
                f.write_text(f.read_text() + text)
            else:
                f.write_text(text)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "--no-gpg-sign", "-m", spec["message"],
             env_dates=spec["date"] + " +0000")
    return repo


def clean_py_lines(n: int, tag: str, start: int = 0) -> list[str]:
    """N distinct python lines with no masking constructs."""
    return [f"def fn_{tag}_{start + i}(value): return compute(value, {start + i})"
            for i in range(n)]


def masked_py_lines(n_clean: int, n_masked: int, tag: str, start: int = 0) -> list[str]:
    """Clean lines plus hard-masking constructs (bare except: pass swallows)."""
    lines = clean_py_lines(n_clean, tag, start)
    for i in range(n_masked):
        lines += [
            f"def risky_{tag}_{i}(value):",
            "    try:",
            "        return compute(value)",
            "    except Exception: pass",
        ]
    return lines
