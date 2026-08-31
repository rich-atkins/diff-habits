"""diff-habits CLI: duplication and error-masking from diff contents."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from git_habits.exclude import Excluder

from .collect import AddedChunk, DiffCollectError, collect
from .duplication import DuplicationDetector
from .masking import MaskingDetector

# Evidence floor (v0.2): masking events are rare (published densities run
# roughly 0.2-4 per 1k added lines), so a rate over a few hundred lines is
# noise wearing a number's clothes. Below the floor the rate is refused, not
# reported; the raw counts stay visible. Override with --min-evidence-lines.
MIN_EVIDENCE_LINES = 500

_RATE_KEYS = (
    "masking_hard_per_kloc", "masking_soft_per_kloc",
    "duplication_per_million_added", "duplication_pct_of_meaningful",
)


def _insufficiency(r: dict, min_lines: int) -> dict[str, str]:
    """Rate keys whose denominator is below the evidence floor (unknown != zero)."""
    if r["added_lines"] >= min_lines:
        return {}
    reason = f"n={r['added_lines']} added lines, need >={min_lines}"
    return {k: reason for k in _RATE_KEYS}


def _analyse(chunks: list[AddedChunk]) -> dict:
    dup = DuplicationDetector()
    mask = MaskingDetector()
    for c in chunks:
        dup.add(c.lines)
        mask.add(c.path, c.lines)
    d, m = dup.result, mask.result
    return {
        "commits": len({c.sha for c in chunks}),
        "files": len({c.path for c in chunks}),
        "added_lines": d.changed_lines_seen,
        "meaningful_lines": d.meaningful_lines_seen,
        "duplicate_blocks": d.blocks,
        "duplicated_lines": d.duplicated_lines,
        "duplication_per_million_added": round(d.per_million_changed, 1),
        "duplication_pct_of_meaningful": round(d.pct_of_meaningful, 2),
        "masking_hard": m.hard_hits,
        "masking_hard_per_kloc": round(m.hard_per_kloc, 2),
        "masking_soft": m.soft_hits,
        "masking_soft_per_kloc": round(m.soft_per_kloc, 2),
        "masking_by_pattern": dict(sorted(m.by_pattern.items(), key=lambda kv: -kv[1])),
        "duplication_examples": d.examples,
    }


def _render(label: str, r: dict, show_duplication: bool = False,
            insuff: dict[str, str] | None = None) -> str:
    insuff = insuff or {}
    top = list(r["masking_by_pattern"].items())[:5]

    def _rate(key: str, text: str) -> str:
        return f"insufficient ({insuff[key]})" if key in insuff else text

    lines = [
        f"  {label}",
        f"    commits / files      {r['commits']:,} / {r['files']:,}",
        f"    added lines          {r['added_lines']:,}  ({r['meaningful_lines']:,} meaningful)",
        f"    error masking (hard) {r['masking_hard']:,}  "
        + _rate("masking_hard_per_kloc", f"({r['masking_hard_per_kloc']} per 1k added)"),
        f"    error masking (soft) {r['masking_soft']:,}  "
        + _rate("masking_soft_per_kloc", f"({r['masking_soft_per_kloc']} per 1k added)"),
        "    top patterns         " + (", ".join(f"{k}={v}" for k, v in top) or "none"),
    ]
    if show_duplication:
        lines += [
            f"    [exp] dup blocks     {r['duplicate_blocks']:,}  ({r['duplicated_lines']:,} lines)",
            "    [exp] duplication    " + _rate(
                "duplication_per_million_added",
                f"{r['duplication_per_million_added']} per million added"
                f"   |  {r['duplication_pct_of_meaningful']}% of meaningful"),
        ]
    return "\n".join(lines)


def _collect(args, since=None, until=None) -> list[AddedChunk]:
    return collect(
        args.repo,
        Excluder(extra=args.exclude or []),
        author=args.author,
        since=since if since is not None else args.since,
        until=until if until is not None else args.until,
        all_refs=args.all_refs,
    )


def cmd_scan(args) -> int:
    r = _analyse(_collect(args))
    insuff = _insufficiency(r, args.min_evidence_lines)
    if args.json:
        print(json.dumps({**r, "insufficient": insuff}, indent=2))
        return 0
    print("\ndiff-habits scan\n")
    print(_render(args.label or "selection", r, args.experimental_duplication, insuff))
    _footer(args.experimental_duplication)
    return 0


def _just_before(split: str) -> str:
    """One second before the split instant, used as BOTH window edges.

    Measured behaviour (pinned by the boundary test): git's --until is
    inclusive (<=) and --since is exclusive (>). Using the raw split on both
    sides puts a commit at exactly the split instant in the BEFORE window,
    while git-habits' compare puts it AFTER (>= split) — the two tools would
    disagree about the same commit. Anchoring both edges at split-1s gives:
    before = date <= split-1s, after = date > split-1s, so the boundary commit
    lands exactly once, in AFTER, matching git-habits."""
    d = datetime.fromisoformat(split)
    return (d - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")


def cmd_compare(args) -> int:
    # Fail closed per window: an empty window is a failed measurement, and the
    # reader deserves to know WHICH window was empty (v0.1 aborted on the first
    # collect with a generic error before even reaching the second).
    refused = []
    before = after = None
    try:
        before = _analyse(_collect(args, until=_just_before(args.split)))
    except DiffCollectError:
        refused.append(args.before_label)
    try:
        after = _analyse(_collect(args, since=_just_before(args.split)))
    except DiffCollectError:
        refused.append(args.after_label)
    if refused:
        which = " and ".join(f"'{r}'" for r in refused)
        print(f"comparison refused: the {which} window has no added lines. "
              f"Check --author/--since/--until/--split; an empty window compared "
              f"against a real one produces fiction, not deltas.", file=sys.stderr)
        return 1

    ib = _insufficiency(before, args.min_evidence_lines)
    ia = _insufficiency(after, args.min_evidence_lines)
    if args.json:
        print(json.dumps({"split": args.split, "before": before, "after": after,
                          "insufficient": {"before": ib, "after": ia}}, indent=2))
        return 0
    print(f"\ndiff-habits compare  split at {args.split}\n")
    print(_render(args.before_label, before, args.experimental_duplication, ib))
    print()
    print(_render(args.after_label, after, args.experimental_duplication, ia))
    print("\n  deltas (after vs before)")
    rows = [("masking_hard_per_kloc", "masking hard /1k"),
            ("masking_soft_per_kloc", "masking soft /1k")]
    if args.experimental_duplication:
        rows += [("duplication_per_million_added", "[exp] duplication /M"),
                 ("duplication_pct_of_meaningful", "[exp] duplication %")]
    for key, lbl in rows:
        if key in ib or key in ia:
            side = "both windows" if (key in ib and key in ia) else (
                "before window" if key in ib else "after window")
            print(f"    {lbl:<22} insufficient evidence in {side} ({ib.get(key) or ia.get(key)})")
            continue
        b, a = before[key], after[key]
        pct = f"{((a - b) / b * 100):+.0f}%" if b else "n/a"
        print(f"    {lbl:<22} {b:>10} -> {a:<10} {pct}")
    _footer(args.experimental_duplication)
    return 0


def _footer(showed_duplication: bool = False) -> None:
    if showed_duplication:
        print("\n  ! THE DUPLICATION FIGURES ABOVE ARE EXPERIMENTAL AND NOT COMPARABLE TO")
        print("    PUBLISHED RESEARCH. They count any 5-line sequence recurring anywhere in")
        print("    the history walked, conflating real copy/paste with code re-added after a")
        print("    refactor and with ordinary boilerplate, and read roughly three orders of")
        print("    magnitude high. Use the trend between two periods at most; never quote")
        print("    the absolute number. A codebase-snapshot implementation is planned.")
    print("\n  Line-level move detection (the 'refactoring collapse' signal) is NOT")
    print("  measured here. It is a similarity-matching problem, and an approximation")
    print("  would produce numbers incomparable with published research. See README.\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="diff-habits",
        description="Duplication and error-masking measured from diff contents. Local only.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn in (("scan", cmd_scan), ("compare", cmd_compare)):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--author")
        p.add_argument("--since")
        p.add_argument("--until")
        p.add_argument("--all-refs", action="store_true")
        p.add_argument("--exclude", action="append")
        p.add_argument("--json", action="store_true")
        p.add_argument("--experimental-duplication", action="store_true",
                       help="include the experimental duplication metric. It is NOT comparable\n"
                            "to published figures and reads roughly 1000x high. Trend only.")
        p.add_argument("--min-evidence-lines", type=int, default=MIN_EVIDENCE_LINES,
                       help="added-line floor below which rates report as 'insufficient' "
                            f"instead of a number (default {MIN_EVIDENCE_LINES})")
        if name == "scan":
            p.add_argument("--label")
        else:
            p.add_argument("--split", required=True)
            p.add_argument("--before-label", default="before")
            p.add_argument("--after-label", default="after")
        p.set_defaults(fn=fn)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except DiffCollectError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
