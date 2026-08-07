# The no-speculation arm was forced eager on every decode step

Date: 2026-08-06 America/Toronto

Status: **defect found and fixed. The 12.1-12.3 tok/s no-speculation figure was
never a measurement of the graph path; the arm captured and replayed nothing,
and the run directory recorded that fact at the time.**

## The claim that was wrong

[`2026-08-04-no-speculation-on-the-graph-path.md`](2026-08-04-no-speculation-on-the-graph-path.md)
states that the no-drafter arm "reaches the breakable-graph path for the first
time" and "now runs the same 291-segment, 145-break structure as the verifier".

Neither is true. Two independent pieces of evidence, both already sitting in
`20260804-nospec-warm-3/`:

| evidence | value | meaning |
| :--- | ---: | :--- |
| `grep -Fc 'BreakableCUDAGraphCapture(graphs=' server.log` | **0** | nothing was ever captured or replayed |
| `cleanup-status.txt` `original_status` | **2** | the runner `die`d, and 2 is `die`'s only exit |

The runner's topology audit (added 2026-08-02, `13b75d7a3`) requires eight
topology lines -- capture and replay on each of four ranks -- and got zero. The
benchmark had already written `PASS` to `bench.stdout` by then, because the
audit runs after the benchmark completes. The throughput numbers were read off
that `bench.stdout` and the runner's own verdict was not.

## The defect

`_laguna_m8_eligible` in `gpu_model_runner.py` gated on the decoding request
being a **key** of the scheduler's speculative-token map:

```python
req_id = self.input_batch.req_ids[0]
spec_tokens = scheduler_output.scheduled_spec_decode_tokens
return (
    list(spec_tokens) == [req_id]
    and len(spec_tokens[req_id]) == envs.VLLM_XPU_LAGUNA_EXACT_MAX_M - 1
    ...
)
```

The scheduler only creates that key for a request that actually carries draft
tokens (`scheduler.py:645`, `if request.spec_token_ids:`). **With no drafter the
map is empty**, so `list(spec_tokens)` is `[]`, the predicate is false, and it
is false on every single decode step.

What that predicate feeds is not a diagnostic. It is:

```python
force_eager=(
    envs.VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH
    and not laguna_m8_breakable_graph_eligible
),
```

So with `VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1` -- which the arm sets, and which
is what "the graph arm" *means* -- every no-speculation decode step was
**explicitly forced eager**. Turning the graph selector on is what turned the
graphs off.

A second, independent term blocked the same path: the capture filter requires
`xpu_exact_spec_verifier is True`, and that flag is
`len(scheduled_spec_decode_tokens) > 0`, false for the same reason.

## Why `ALLOW_NO_SPEC` did not help

`VLLM_XPU_LAGUNA_ALLOW_NO_SPEC` waives the three drafting terms in the
**startup** contract, so the server boots with the graph selectors on. It has no
bearing on the **runtime** eligibility predicate, which is a different check in
a different file. The arm therefore started cleanly, logged nothing unusual,
reported plausible throughput, and ran eager throughout. That is the failure
mode that made it look like a measurement.

## The fix

Require the draft **count** rather than the key's presence:

```python
return (
    set(spec_tokens) <= {req_id}
    and len(spec_tokens.get(req_id, ()))
    == envs.VLLM_XPU_LAGUNA_EXACT_MAX_M - 1
    and scheduler_output.num_scheduled_tokens.get(req_id)
    == envs.VLLM_XPU_LAGUNA_EXACT_MAX_M
)
```

This is **unchanged above width 1**: `M-1 >= 1` drafts cannot be present without
the key, so every step admitted before is admitted now and no new one is. The
only new admission is width 1 with zero drafts, which is exactly what "no
speculation" means.

The capture filter's verifier term is relaxed the same way and only at width 1,
where a single row is exact by construction -- the same reason
`_xpu_is_exact_decode_or_verifier_rows` already returns `True` for one row
without consulting the flag.

No kernel, dtype, or quantisation behaviour changes. This is a scheduling-path
fix.

Committed as `63da5e0ea`, with three tests: the width-1 admission, a guard that
an absent request is still rejected above width 1, and a guard that the filter
still demands the verifier flag above width 1.

## What this does not fix

The selectors the `qdepth` profile disables are mostly **not** recoverable at
M=1, so the "de-optimised floor" caveat in the 2026-08-04 note was
overstated in the other direction -- there is much less left on the table than
it implies:

| selector | status at M=1, no drafter |
| :--- | :--- |
| `DFLASH_CONTEXT_KV_WORKSPACE`, `DFLASH_FP8_W8A16`, `DFLASH_SEGMENTED_GRAPH`, `DFLASH_INLINE_ATTENTION_GRAPHS` | inapplicable -- there is no drafter |
| `DECODE_GRF128`, `DECODE_TRANSPOSED_SCALES` | inert: host dispatch requires `total_m == 120`, i.e. 12 rows x top-10 |
| `MWIDE_BF16_ROUTER_TOPK` | blocked: requires `EXACT_MAX_M == 12` |
| `M8_BF16_ROUTER_TOPK` | blocked: requires eager, or the width-12 graph selector |
| `M12_SHARED_ELEMENTWISE` | blocked: contract requires DFlash depth 11 |
| `M12_MAPPED_GATHER_SCALE_ADD`, `WIDE_PREFILL_QKNORM_ROPE` | **dead**: read nowhere in either repo |

The last row is worth recording on its own: two selectors the depth-sweep
profile carefully sets to 0 do not exist. That makes ten and eleven in this
campaign's tally of built-but-unwired or referenced-but-unimplemented artifacts.

## Boundaries

The zero-topology-line and `original_status=2` facts are from the sealed
`20260804-nospec-warm-3` run directory. The predicate analysis is from the fork
at `68a4965de`; the fix is `63da5e0ea`. No quantisation change, and no caching
or speculation setting used to inflate any number -- the arm has no speculation
at all, which is the point. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
