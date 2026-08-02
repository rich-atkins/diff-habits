"""Block duplication: runs of repeated meaningful lines.

Follows GitClear's published definition of a duplicated block as five or more
consecutive repeated meaningful lines, and normalises the result per million
changed lines so it can sit next to their figures.

What this does NOT do is detect a block of lines *moving* from one file to another.
That is the signal behind the widely quoted "refactoring has collapsed" claim, and
it is a similarity-matching problem rather than a hashing one. A naive version
produces numbers that look plausible and are not comparable to anyone else's, which
is worse than not having it. It is out of scope and said so in the README.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .normalise import meaningful_lines

BLOCK_SIZE = 5


@dataclass
class DuplicationResult:
    blocks: int = 0
    duplicated_lines: int = 0
    meaningful_lines_seen: int = 0
    changed_lines_seen: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def per_million_changed(self) -> float:
        if not self.changed_lines_seen:
            return 0.0
        return 1_000_000.0 * self.duplicated_lines / self.changed_lines_seen

    @property
    def pct_of_meaningful(self) -> float:
        if not self.meaningful_lines_seen:
            return 0.0
        return 100.0 * self.duplicated_lines / self.meaningful_lines_seen


class DuplicationDetector:
    """Finds repeated blocks across everything it is shown.

    State accumulates: feed it the added lines of every commit in a window and it
    reports repetition across that whole window, not merely within single commits.
    """

    def __init__(self, block_size: int = BLOCK_SIZE) -> None:
        self.block_size = block_size
        self._seen: dict[tuple[str, ...], int] = {}
        self.result = DuplicationResult()

    def add(self, lines: list[str], keep_example: bool = True) -> int:
        """Feed one file's added lines. Returns lines counted as duplicated."""
        self.result.changed_lines_seen += len(lines)
        meaningful = meaningful_lines(lines)
        self.result.meaningful_lines_seen += len(meaningful)
        if len(meaningful) < self.block_size:
            return 0

        texts = [t for _, t in meaningful]
        dup_here = 0
        i = 0
        while i + self.block_size <= len(texts):
            key = tuple(texts[i : i + self.block_size])
            if key in self._seen:
                # Extend greedily so a 12-line repeat counts as 12, not as
                # eight overlapping 5-line windows.
                run = self.block_size
                while (
                    i + run < len(texts)
                    and tuple(texts[i + run - self.block_size + 1 : i + run + 1]) in self._seen
                ):
                    run += 1
                dup_here += run
                self.result.blocks += 1
                if keep_example and len(self.result.examples) < 5:
                    self.result.examples.append(" / ".join(key[:2])[:120])
                i += run
                continue
            self._seen[key] = 1
            i += 1

        self.result.duplicated_lines += dup_here
        return dup_here
