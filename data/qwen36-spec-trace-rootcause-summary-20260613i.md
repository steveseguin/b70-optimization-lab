# Qwen3.6 Spec Trace Root-Cause Refresh 20260613i

Purpose: preserve the current speculative-decoding failure shape before the
next implementation attempt. This is a trace-only analysis; it does not change
the accepted endpoint or promote a speed result.

## Script Change

`scripts/replay-qwen36-spec-trace.py` now separates three suppressed-bonus
follow-up cases:

- `next_schedules_suppressed_bonus`: the proposer fed the suppressed bonus back
  as the next draft.
- `next_replays_suppressed_bonus`: the verifier's next generated first token
  matched the suppressed bonus.
- `next_accepts_suppressed_bonus`: the next scheduled draft was the suppressed
  bonus and the verifier accepted/emitted it.

The JSON rows also include `computed_minus_tokens_after_output` so we can spot
state where the worker/scheduler boundary is behind the emitted sequence or
where stale unemitted KV may have stayed live.

## Replayed Traces

| trace | rows | schedule mismatches | accept mismatches | accounting mismatches | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-nograph-20260612c` | 6 | 0 | 2 | 0 | Proposer reschedules the suppressed bonus, but target rejects it. Accounting alone is not enough. |
| `qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-keepcomputed-nograph-20260612d` | 4 | 0 | 2 | 2 | Keeping computed tokens advanced leaves stale/uncommitted state and also fails acceptance. |
| `qwen36-quark-int8-tp4-oracle1-nobonus-recompute-nograph-20260612f` | 20 | 18 | 18 | 0 | Skipping the next draft/recompute path disrupts scheduling and does not restore exact acceptance. |
| `qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-jsonl-20260611` | 6 | 2 | 2 | 0 | Non-oracle ngram path has both proposer/schedule misses and verifier-state misses. |

Generated artifacts:

- `data/qwen36-spec-trace-rootcause-oracle1-nobonus-cachefilter-v2-20260613i.{json,md}`
- `data/qwen36-spec-trace-rootcause-oracle1-keepcomputed-v2-20260613i.{json,md}`
- `data/qwen36-spec-trace-rootcause-oracle1-recompute-v2-20260613i.{json,md}`
- `data/qwen36-spec-trace-rootcause-ngram5-nobonus-accounting-v2-20260613i.{json,md}`

## Main Finding

For the oracle cache-filter trace, schedule mismatches are `0` but accept
mismatches are `2`: the suppressed bonus token is fed back as the next draft,
then the exact target rejects it. That means the failure is not draft quality.
It is a verifier/KV/input-position state problem around suppressed bonus
handling, especially after consecutive full-accept rows.

The current no-bonus diagnostic is trying to retrofit "no user-visible bonus"
after the standard target pass has already produced a bonus. The traces show
that simply trimming sampled IDs and adjusting `num_computed_tokens` does not
leave the scheduler and worker token/KV caches aligned for the next verifier
step.

## Next Implementation Targets

1. **Worker/scheduler boundary trace.** Re-run the oracle cache-filter case with
   the worker COW trace enabled and inspect `token_ids_cpu`,
   `num_tokens_no_spec`, `num_computed_tokens_cpu`, scheduler
   `num_computed_tokens`, and cache write ranges across consecutive
   full-accept rows.
2. **Consecutive full-accept repair.** Test a targeted fix for the second
   consecutive suppressed-bonus row. The current evidence suggests the first
   suppression can replay correctly, then the following row lands one token off.
3. **Explicit no-bonus sampler mode.** Prefer a real sampler/rejection-sampler
   mode that validates drafts without exposing or committing the full-accept
   bonus, rather than trimming the bonus after the fact in two different
   caches.
4. **No promotion until oracle k=1 parity.** Do not return to wider ngram/MTP
   speculation until the oracle one-draft path has zero schedule mismatches,
   zero accept mismatches, zero accounting mismatches, and accepted-output
   parity against the no-spec baseline.

