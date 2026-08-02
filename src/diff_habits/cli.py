"""diff-habits CLI: duplication and error-masking from diff contents."""
from __future__ import annotations

import argparse
import json
import sys

from git_habits.exclude import Excluder

from .collect import AddedChunk, DiffCollectError, collect
from .duplication import DuplicationDetector
from .masking import MaskingDetector


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


def _render(label: str, r: dict, show_duplication: bool = False) -> str:
    top = list(r["masking_by_pattern"].items())[:5]
    lines = [
        f"  {label}",
        f"    commits / files      {r['commits']:,} / {r['files']:,}",
        f"    added lines          {r['added_lines']:,}  ({r['meaningful_lines']:,} meaningful)",
        f"    error masking (hard) {r['masking_hard']:,}  ({r['masking_hard_per_kloc']} per 1k added)",
        f"    error masking (soft) {r['masking_soft']:,}  ({r['masking_soft_per_kloc']} per 1k added)",
        "    top patterns         " + (", ".join(f"{k}={v}" for k, v in top) or "none"),
    ]
    if show_duplication:
        lines += [
            f"    [exp] dup blocks     {r['duplicate_blocks']:,}  ({r['duplicated_lines']:,} lines)",
            f"    [exp] duplication    {r['duplication_per_million_added']} per million added"
            f"   |  {r['duplication_pct_of_meaningful']}% of meaningful",
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
    if args.json:
        print(json.dumps(r, indent=2))
        return 0
    print("\ndiff-habits scan\n")
    print(_render(args.label or "selection", r, args.experimental_duplication))
    _footer(args.experimental_duplication)
    return 0


def cmd_compare(args) -> int:
    before = _analyse(_collect(args, until=args.split))
    after = _analyse(_collect(args, since=args.split))
    if args.json:
        print(json.dumps({"split": args.split, "before": before, "after": after}, indent=2))
        return 0
    print(f"\ndiff-habits compare  split at {args.split}\n")
    print(_render(args.before_label, before, args.experimental_duplication))
    print()
    print(_render(args.after_label, after, args.experimental_duplication))
    print("\n  deltas (after vs before)")
    rows = [("masking_hard_per_kloc", "masking hard /1k"),
            ("masking_soft_per_kloc", "masking soft /1k")]
    if args.experimental_duplication:
        rows += [("duplication_per_million_added", "[exp] duplication /M"),
                 ("duplication_pct_of_meaningful", "[exp] duplication %")]
    for key, lbl in rows:
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
