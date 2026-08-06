# Example output

So you can see what to expect before running it on your own history, here is
`diff-habits` run against a small **seeded demo repository**: eight commits by one
author across two periods — four hand-coded (Jan–Mar 2026) and four AI-assisted
(May–Jul 2026) — split at `2026-04-13`. The later commits deliberately contain a
handful of masking constructs (an empty `catch`, a `@ts-ignore`, an `as any`, a
stubbed `return null // TODO`).

The numbers are tiny on purpose. It is a fixture for showing the *shape* of the
report, not a dataset to draw conclusions from.

## `scan` — one period

```text
diff-habits scan --repo ./demo --author "dev@example.com"

diff-habits scan

  selection
    commits / files      8 / 7
    added lines          62  (43 meaningful)
    error masking (hard) 12  (193.55 per 1k added)
    error masking (soft) 3  (48.39 per 1k added)
    top patterns         any_cast_ts=4, stub_return=4, empty_catch_js=2, ts_suppress=2, todo_marker=2
```

`meaningful` added lines are what remain after blank lines, braces, comments and
imports are stripped, so the per-1k rates are not diluted by formatting.

## `compare` — before and after a split

```text
diff-habits compare --repo ./demo --author "dev@example.com" --split 2026-04-13

diff-habits compare  split at 2026-04-13

  before
    commits / files      4 / 4
    added lines          22  (17 meaningful)
    error masking (hard) 1  (45.45 per 1k added)
    error masking (soft) 0  (0.0 per 1k added)
    top patterns         stub_return=1

  after
    commits / files      4 / 3
    added lines          40  (26 meaningful)
    error masking (hard) 11  (275.0 per 1k added)
    error masking (soft) 3  (75.0 per 1k added)
    top patterns         any_cast_ts=4, stub_return=3, empty_catch_js=2, ts_suppress=2, todo_marker=2

  deltas (after vs before)
    masking hard /1k            45.45 -> 275.0      +505%
    masking soft /1k              0.0 -> 75.0       n/a
```

The `+505%` is the kind of jump this tool exists to surface — but read the README's
"What this tool cannot tell you" first: masking density is dominated by problem
domain, so this only means something when you compare a codebase with *itself* across
time, never one repo against another.
