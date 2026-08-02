"""Error-masking constructs: code that suppresses a signal rather than handling it.

The distinction that matters is between handling a failure and hiding one. A catch
block that logs, retries or rethrows is engineering. A catch block that swallows the
exception silently, a `?.` chain that turns a missing object into `undefined` and
carries on, a stubbed method returning a placeholder: those remove the evidence that
something went wrong.

The industry finding this tracks is a rise in these constructs alongside AI-assisted
authorship. Whether that is AI's doing or the deadline's, the count is measurable.

Honest limitation, stated in the README as well as here: these are regexes, not a
parser. They over-count (a legitimate optional-chain on a genuinely optional field)
and under-count (a swallow spread across several lines). Treat the number as an
indicator whose *trend* is meaningful, not as an audit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# (name, pattern, languages) - matched against single added lines.
PATTERNS: list[tuple[str, re.Pattern, tuple[str, ...]]] = [
    ("empty_catch_js", re.compile(r"catch\s*(\([^)]*\))?\s*\{\s*\}"), (".js", ".ts", ".tsx", ".jsx", ".java", ".cs")),
    ("catch_ignore_comment", re.compile(r"catch\s*(\([^)]*\))?\s*\{\s*(//|/\*)\s*(ignore|noop|nothing|swallow)", re.I),
     (".js", ".ts", ".tsx", ".jsx", ".java", ".cs")),
    ("except_pass_py", re.compile(r"except[^:]*:\s*pass\s*$"), (".py",)),
    ("except_bare_py", re.compile(r"except\s*:\s*$"), (".py",)),
    ("rescue_nil_rb", re.compile(r"rescue\s*(=>\s*\w+)?\s*$|rescue\s+nil"), (".rb",)),
    ("err_ignored_go", re.compile(r"^\s*_\s*(,\s*_\s*)*[:=]+.*\berr\b|^\s*_\s*=\s*\w+\("), (".go",)),
    ("optional_chain", re.compile(r"\?\."), (".js", ".ts", ".tsx", ".jsx")),
    ("nullish_default", re.compile(r"\?\?\s*(\[\]|\{\}|''|\"\"|0|null|undefined)"), (".js", ".ts", ".tsx", ".jsx")),
    ("any_cast_ts", re.compile(r"\bas\s+any\b|:\s*any\b"), (".ts", ".tsx")),
    ("ts_suppress", re.compile(r"@ts-(ignore|expect-error|nocheck)"), (".ts", ".tsx")),
    ("lint_suppress", re.compile(r"eslint-disable|# noqa|# type:\s*ignore|#\s*pylint:\s*disable"),
     (".js", ".ts", ".tsx", ".jsx", ".py")),
    ("stub_return", re.compile(r"\breturn\s+(None|null|nil|\[\]|\{\}|''|\"\")\s*(#|//)?\s*(TODO|stub|placeholder)?", re.I),
     (".py", ".js", ".ts", ".tsx", ".go", ".rb")),
    ("todo_marker", re.compile(r"\b(TODO|FIXME|HACK|XXX)\b"), ()),
]

# Constructs that are legitimate often enough that counting them as masking would be
# misleading on its own. Reported separately so the headline stays defensible.
SOFT = {"optional_chain", "nullish_default", "todo_marker"}


@dataclass
class MaskingResult:
    hard_hits: int = 0
    soft_hits: int = 0
    lines_seen: int = 0
    by_pattern: dict[str, int] = field(default_factory=dict)

    @property
    def hard_per_kloc(self) -> float:
        return 1000.0 * self.hard_hits / self.lines_seen if self.lines_seen else 0.0

    @property
    def soft_per_kloc(self) -> float:
        return 1000.0 * self.soft_hits / self.lines_seen if self.lines_seen else 0.0


def _applies(pattern_langs: tuple[str, ...], path: str) -> bool:
    if not pattern_langs:
        return True
    return any(path.endswith(ext) for ext in pattern_langs)


class MaskingDetector:
    def __init__(self) -> None:
        self.result = MaskingResult()

    def add(self, path: str, lines: list[str]) -> None:
        self.result.lines_seen += len(lines)
        for line in lines:
            for name, rx, langs in PATTERNS:
                if not _applies(langs, path):
                    continue
                if rx.search(line):
                    self.result.by_pattern[name] = self.result.by_pattern.get(name, 0) + 1
                    if name in SOFT:
                        self.result.soft_hits += 1
                    else:
                        self.result.hard_hits += 1
