# diff-habits

**Is your codebase quietly hiding its own failures?**

Counts error-masking constructs in your own diff history, and compares any two periods.
An empty catch block, an `except: pass`, a `@ts-ignore`: each one removes the evidence
that something went wrong. This tells you whether you are adding more of them than you
used to.

Companion to [git-habits](https://github.com/uxdw/git-habits), which measures commit
and refactoring habits from metadata alone. `git-habits` never reads your source.
`diff-habits` does, which is why it is a separate tool rather than a flag: you can run
`git-habits` on an employer's repository without a conversation, and this one is a
different decision.

Reads locally, emits only counts. Nothing is uploaded and there is no network access.

## Install

```bash
git clone https://github.com/uxdw/diff-habits && cd diff-habits
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

It depends on `git-habits`, so exclusion rules stay identical between the two tools and
their numbers remain comparable.

## Use

```bash
# one period
diff-habits scan --repo . --author "you@example.com"

# before and after a change in how you work
diff-habits compare --repo . --author "you@example.com" --split 2026-04-13
```

## What it measures

Only **added** lines are examined. A deletion cannot introduce a swallowed error, and
counting both sides would double-count a moved line.

**Hard masking** removes a signal outright:

| Pattern | Example |
|---|---|
| Empty catch | `catch (e) {}` |
| Silenced exception | `except ValueError: pass`, `rescue nil` |
| Suppressed checking | `@ts-ignore`, `# noqa`, `eslint-disable` |
| Weakened typing | `as any` |
| Stubbed return | `return None  # TODO` |
| Discarded error | Go's `_` assignment over an `err` |

**Soft masking** is reported separately because it is legitimate often enough that
counting it in the headline would mislead: optional chaining, nullish defaults, TODO
markers. A `?.` on a genuinely optional field is good code. Twenty of them in a row
usually is not, and that is a judgement the tool declines to make for you.

Both are normalised per thousand added lines.

## What this tool cannot tell you

- **These are regexes, not a parser.** They over-count a legitimate optional chain and
  under-count a swallow spread across several lines. The *trend* between two periods is
  the meaningful part; a single absolute number is not an audit.
- **Masking density is dominated by domain.** A scraper or an LLM pipeline is defensively
  coded because networks and models genuinely fail. Comparing error handling across
  different problem domains and attributing the gap to who wrote the code will mislead
  you. Compare a codebase with itself.
- **A rise is not automatically bad.** Sometimes hardening is the correct response to a
  flaky dependency. The number tells you where to look, not what to conclude.
- **It cannot detect AI**, only when things changed.

## Not measured, deliberately

**Line-level move detection** — the signal behind the widely repeated claim that
refactoring has collapsed. It is a similarity-matching problem rather than a hashing
one, and a naive implementation produces numbers that look plausible while being
incomparable with the published research they would be quoted against. Better to say
so than to ship an approximation.

**Block duplication** is implemented but **off by default** behind
`--experimental-duplication`. The current approach counts any five-line sequence
recurring anywhere in the history it walks, which conflates genuine copy/paste with
code re-added after a refactor and with ordinary boilerplate. Measured against real
repositories it reads roughly three orders of magnitude above codebase-snapshot
figures. It is useful as a trend between two periods of the same repository and
useless as an absolute number. A snapshot-based implementation is the planned fix.

Both of those are in this section rather than an issue tracker because a tool that
quietly ships a broken metric is worse than one that admits to a gap.

## Licence

MIT, © Richard Atkins.
