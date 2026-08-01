# Laguna target inline-gather prefix bisection

Date: 2026-08-01 America/Toronto

Status: **complete; slot 48 is the first unsafe captured boundary. No score was
run or authorized.**

## Motivation

The protected BF16-KV record remains `125.4619731637751 tok/s` conventional
with exact target topology `146/145`. Capturing all 96 target gathers reduced
that topology to `50/49`, but both the output-only V1 and fixed-input/output V2
eventually changed tokens. V2 preserved 176 exact output tokens before its
first mismatch, while an independent synthetic M12 composition probe proved
96 raw-exact gather compositions.

Those results do not establish that every model gather is unsafe. They support
a bounded prefix diagnostic that can both localize the failure and discover an
exact partial launch-removal treatment.

## Treatment

Add a diagnostic-only integer `LAGUNA_TARGET_INLINE_GATHER_LIMIT`, effective
only when the existing default-off target-inline-gather selector is enabled.
For a limit `N`:

- slots `[0,N)` use V2's fixed input/output capture path;
- slots `[N,96)` remain the protected eager collective callbacks;
- the embedding all-reduce remains eager;
- model arithmetic and rank-ordered BF16 reduction are unchanged;
- fixed inputs are allocated only for captured slots;
- replay requires exactly `97-N` eager collective callbacks; and
- audited target topology must be exactly `146-N / 145-N` on every rank.

The selector-off/default record path must remain byte-for-byte behaviorally
unchanged. Invalid, out-of-range, or selector-off nondefault limits fail closed.

## Ordered gate

1. Implement and inspect the source in a new worktree based on fixed-input V2.
   Pass Ruff, compileall, whitespace, selector-off tests, full-96 tests, mixed
   capture/eager count tests, fixed-buffer ownership tests, and topology math.
2. Run exactly one non-scored, changing-request smoke at `N=48`. Persist raw
   responses before assertions. Require q=1 token prefixes, `cached_tokens=0`,
   normal DFlash acceptance, target `98/97`, draft `14/13`, four-rank activation,
   and clean teardown.
3. If `N=48` is exact, the next diagnostic limit is 72. If it is inexact, the
   next limit is 24. Continue only by halving the remaining prefix interval;
   never retry an unchanged limit. Every leg is a fresh service and reports its
   first result.
4. Any hang, collective/device error, pointer/count drift, or dirty teardown
   stops the ladder. Do not reset, reload, unbind, FLR, delete shared memory,
   or reboot.
5. A prefix passing 400 tokens is diagnostic evidence, not throughput or full
   correctness evidence. It authorizes a separate full exactness gate before
   any score. No endpoint score is authorized by this note.

The frozen model, draft, BF16 KV, width 12, DFlash depth 11, teacher, prompts,
sampling, cache policy, verification, and metric remain unchanged.

## Result

The source at vLLM `3dafc2a51` implemented a validated mixed captured/eager
prefix and derived graph topology from the same limit. One initial `N=48`
attempt never reached the treatment because an inherited V1 topology guard
still demanded `50/49`; it observed the correct `98/97`, aborted, and cleaned
up. That plumbing failure is not a model result. After the guard fix and
focused tests, the first-result ladder was:

| Captured prefix | Target topology | Result | First mismatch |
| ---: | ---: | --- | ---: |
| 48 | 98/97 | pass, two 400-token requests | none |
| 72 | 74/73 | fail request 0 | 374 |
| 60 | 86/85 | fail request 0 | 168 |
| 54 | 92/91 | fail request 0 | 50 |
| 51 | 95/94 | fail request 0 | 49 |
| 49 | 97/96 | fail request 0 | 96 |

Every model result had 400 returned tokens, `cached_tokens=0`, real DFlash
speculation, the expected topology on all ranks, no device/runtime error, and
clean teardown. The mismatch index is deliberately not treated as a quality
score; pass/fail is the only ordering signal.

Prefix 48 captures slots 0 through 47 and passes. Prefix 49 differs only by
capturing slot 48 and fails. With two gathers per target layer, slot 48 is
layer 24's attention O-projection gather. The next distinct experiment is not
another prefix: retain slot 48 eager and capture the other 95 slots.
