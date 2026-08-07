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

## What it was worth

`20260806-nospec-graphfix-e`, same harness configuration as
`20260804-nospec-warm-3` so the only variable is the vLLM commit. The capture
audit reports **`graphs=146, eager_breaks=145`** -- the audited topology, at
M=1, on all four ranks, captured *and* replayed. The arm reaches the graph path
for the first time, this time for real.

| case | eager (2026-08-04) | graphed (2026-08-06) | step ms | speedup |
| :--- | ---: | ---: | ---: | ---: |
| 8,192 middle (1st, pays capture) | 12.260 | **39.173** | 82 -> 25.5 | 3.20x |
| 32,640 early | 12.213 | **63.533** | 82 -> 15.7 | 5.20x |
| 256 sentinel | 12.128 | **67.521** | 82 -> 14.8 | 5.57x |

Benchmark status `PASS_BASELINE_ORACLE_NOT_TESTED`, all rows `passed=true`,
`cached_tokens_all_zero`, `prompts_unique`. The first case pays graph capture
inside its own first-100-token window, which is why it trails the other two;
the sentinel is the clean short-context figure.

**The step is no longer flat in context** -- 14.8 ms at 256 against 15.7 ms at
32,640 -- but it is very nearly so, which is expected: 36 of 48 layers have a
512-token window, and the 12 full-attention layers read only ~400 MB per rank
at 32K.

## The consequence: speculation is the wrong choice at 32K

Compared at matched positions in the same suite, so warmth and ordering match
(q12 figures from `20260804-eventprofile-q12`):

| position | case | q12, speculative | no-spec, graphed | winner |
| :--- | :--- | ---: | ---: | :--- |
| 1st, cold | 8,192 middle | 7.855 | **39.173** | no-spec, 4.99x |
| 2nd, warm | 32,640 early | 38.425 | **63.533** | **no-spec, 1.65x** |
| 3rd, warm | 256 sentinel | **162.029** | 67.521 | speculative, 2.40x |

Speculation wins at short context by 2.4x and **loses at 32K by 1.65x**. The
32K target was written off as drafter-limited at 1.058 tokens per step; that
diagnosis was right about speculation and wrong about the machine. Turning the
drafter *off* past some context is now the faster configuration, which is the
dynamic-speculation policy the goal statement explicitly permits. Finding the
crossover needs a context sweep (the suite has 1,024 through 32,640); it lies
somewhere between 256 and 32,640.

The cold-first-case penalty is also far worse for q12 (7.855) than for the
no-drafter arm (39.173), because q12 captures a second graph for the drafter
and warms DFlash as well.

## Exactness, with the confounds removed

Three controls, all on sealed run directories.

**The eager path is bitwise stable across the two code versions.**
`20260804-nospec-warm-3` (old tree) against `20260806-nospec-eager-control`
(current tree, `LAGUNA_EAGER_FANOUT=1`): all three cases identical, and 12.151
/ 12.316 / 12.401 tok/s against the old 12.260 / 12.213 / 12.128. **The forty
intervening commits changed neither the arithmetic nor the speed.** The whole
5.2x is the graph path and nothing else.

**The graphed path is deterministic run to run.** Two graphed runs emit
identical `output_token_ids_sha256` and identical `token_ids` for 8,192 middle.

**Eager against graphed, same tree, same day, same driver state:**

| case | tokens | retrieval identical |
| :--- | :--- | :--- |
| 8,192 middle | **identical** | yes |
| 32,640 early | 9 of 128 differ, from index 115 | yes |
| 256 sentinel | **identical** | yes |

So there is one real difference, it is confined to 32K, and it is
reproducible -- the same nine positions from the same index as against the old
tree. It begins at token 115 of 128, **after** the JSON answer has closed at
character 177, and all five retrieval fields parse to identical values on both
paths. It is a divergence in the unconstrained continuation, not in the answer.

The likely mechanism is not replay arithmetic but **KV cache sizing**, which
the graph configuration changes: same 5.34 GiB, but **212,832 tokens eager
against 258,132 graphed**, a 21% difference in per-token footprint and
therefore a different block layout and a different long-context attention
tiling. That it appears only at 32K, where the full-attention layers actually
read a long KV, and not at 8,192 or 256, fits that mechanism and does not fit a
systematic arithmetic change in replay.

**This is not settled, and it should not be quoted as settled.** Pinning bytes
with `LAGUNA_KV_CACHE_BYTES` cannot equalise the two, because what differs is
the per-token cost rather than the budget; separating them needs the KV spec
itself examined. Until then the honest statement is: *the graphed no-speculation
path is bitwise equal to eager at 8,192 and 256, and differs from it at 32,640
in the tail after the answer, deterministically, with the retrieval answer
unchanged.*

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
