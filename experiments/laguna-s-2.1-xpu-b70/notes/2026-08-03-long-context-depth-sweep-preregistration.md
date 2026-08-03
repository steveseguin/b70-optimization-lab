# Laguna long-context draft-depth sweep preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistration plus the launcher and wrapper source it defines;
host-tested only. No XPU, model, endpoint, benchmark, swap change, or recovery
action was performed and none is authorized.**

## Purpose

Decode throughput at long context tracks speculative acceptance almost exactly:

| prompt | decode tok/s | acceptance |
| ---: | ---: | ---: |
| 1,024 | 153.604 | 23.56% |
| 8,192 | 46.810 | 2.34% |
| 32,640 | 39.589 | 0.47% |

At 32,640 tokens DFlash drafts eleven positions and the target accepts about
0.05 tokens per step. Ten of the eleven drafted positions are close to pure
waste, and the target still verifies twelve rows to consume them. The question
is how much decode throughput comes back if the drafter proposes fewer
positions at long context.

Nothing here answers that question. This registers the arms, the budget pin
that makes them comparable, and the stop rules, and it records which arms are
measurable at all on the current source.

## The coupling, and why the budget is pinned

`SpeculativeConfig.max_num_new_slots_for_drafting` returns
`num_speculative_tokens - 1` when `parallel_drafting` is set, and DFlash sets it
(`vllm/config/speculative.py`). `uses_draft_model()` is `method == "draft_model"`,
which DFlash is not, so nothing adds the extra slot. `VllmConfig._set_max_num_
scheduled_tokens` then computes, at `max_num_seqs = 1`:

```
max_num_scheduled_tokens = max_num_batched_tokens - (depth - 1)
```

The scheduler's per-step token budget is that derived value, and the
`min(num_new_tokens, token_budget)` clamp partitions a 32,640-token prompt with
it. The incumbent is `8192 - 10 = 8182`, giving `8182 + 8182 + 8182 + 8094`.

Changing draft depth therefore changes the prefill partition. That is not a
theoretical concern. On 2026-08-02 the `8192 + 8192 + 8192 + 8064` partition was
tested directly and **rejected**: it changed output token IDs and text on all
eight long rows at or above 8,192 prompt tokens, with first mismatches between
output indices 67 and 91. See
[`2026-08-02-scheduler-alignment-result.md`](2026-08-02-scheduler-alignment-result.md).
A naive depth sweep would reproduce that confound and attribute a
partition-driven output change to draft depth.

Every arm therefore pins

```
max_num_batched_tokens = 8182 + (depth - 1)
```

so the derived budget is 8182 and the partition is identical at every depth:

| depth | slots reserved | batched tokens | derived budget | 32,640 partition |
| ---: | ---: | ---: | ---: | :--- |
| 11 | 10 | 8192 | 8182 | 8182 + 8182 + 8182 + 8094 |
| 7 | 6 | 8188 | 8182 | 8182 + 8182 + 8182 + 8094 |
| 3 | 2 | 8184 | 8182 | 8182 + 8182 + 8182 + 8094 |
| 1 | 0 | 8182 | 8182 | 8182 + 8182 + 8182 + 8094 |

`serve_laguna_long_context_nvme.sh` recomputes the derived budget from the
depth actually configured and refuses to launch unless it is exactly 8182. The
`batched = 8202` value stays reserved for the closed alignment treatment and the
depth profile cannot claim it.

Depth 0 is not expressible: `num_speculative_tokens` is declared
`Field(default=None, gt=0)` and is separately rejected at `<= 0`.

## Which arms are actually measurable

The incumbent q12 identity is a sealed depth-11, width-12 contract. Auditing
every exact selector against the fork gives:

| selector | pinned to | measurable at depth 7? |
| :--- | :--- | :--- |
| `MWIDE_BF16_ROUTER_TOPK` | exact width 12 | no |
| `M8_BF16_ROUTER_TOPK` | needs MWIDE unless eager | no |
| `DFLASH_CONTEXT_KV_WORKSPACE` | depth 11 and width 12 | no |
| `DFLASH_FP8_W8A16` / `FP8_Q8` | need the context-KV workspace | no |
| `DFLASH_SEGMENTED_GRAPH` | width 12, filter hard-coded to 12 | no |
| `DFLASH_INLINE_ATTENTION_GRAPHS` | needs the segmented graph | no |
| `M12_SHARED_ELEMENTWISE` | depth 11 exactly | no |
| `M8_SHARED_ELEMENTWISE` | depth 7 exactly | not at depth 11 |
| `M12_MAPPED_GATHER_SCALE_ADD` | needs M12 shared elementwise | no |
| `EXACT_PREFILL_CHUNKS` | width 12 | no |
| `WIDE_PREFILL_QKNORM_ROPE` | width 12, depth 11, batched 8192 | no |
| `M8_BREAKABLE_GRAPH` | `depth == EXACT_MAX_M - 1`, capture size `[M]` | yes |
| `EXACT_SPEC_ATTN`, exact linear M | any width 1..16 | yes |
| `M8_QKNORM_ROPE` | fires only at verifier width 8 or 12 | yes |

The common substrate is the intersection: every selector in the first group is
held **off at every depth, including depth 11**. The depth-11 arm of this sweep
is therefore not the incumbent. It is a de-optimized depth-11 reference that
exists so the depth-7 arm has something legitimate to be compared against.

Two consequences follow, and both are load-bearing.

**Depths 3 and 1 are not cleanly measurable and are refused.** The fused target
QKNorm+RoPE fires only when the row count is 8 or 12
(`hidden_states.shape[0] in (8, 12)` in `models/laguna.py`), and it does not
raise when it misses — it silently falls back. There is likewise no
`laguna_m4_*` or `laguna_m2_*` shared-elementwise op; only the `m8` and `m12`
symbol families exist. A depth-3 or depth-1 arm would quietly run a different,
slower target path, and its decode number would be a mixture of "less drafting"
and "worse target", which is exactly the uninterpretable result this
preregistration exists to prevent. The launcher refuses these depths by name and
states the reason. Making them measurable is a kernel task: width-4 and width-2
fused QKNorm+RoPE and shared-elementwise ops, proved exact first.

**A speculation-off arm is not a ceiling for this path.** With no speculative
config `_set_max_num_scheduled_tokens` never runs, `max_num_scheduled_tokens`
stays `None`, and the scheduler falls back to `max_num_batched_tokens`, so
`batched = 8182` does reproduce the partition. But the candidate role cannot
express it: the launcher mandates `M8_BREAKABLE_GRAPH=1`, whose validator
rejects `speculative_config is None` outright, and the candidate branch always
passes `--speculative-config`. Speculation-off is reachable only as the
`teacher` role, which is enforce-eager, asynchronously scheduled, and has every
fused target selector off. That is a different machine, not the incumbent minus
drafting; it would very likely be slower than the incumbent while doing less
work, and reporting it as a ceiling would be misleading. It is not an arm here.

The launcher change does allow `batched = 8182` for the teacher, for a separate
and real reason: a teacher at 8192 gets budget 8192 and runs the **rejected**
`8192/8064` partition, so any teacher-derived oracle would systematically
disagree with candidate rows at long context. 8182 is what aligns the canonical
q=1 identity to the candidate's partition.

## Consequence: the long-context exactness verdict is suspect

That teacher default is not merely a future hazard. It very likely already
produced a false negative.

The 2026-08-02 long-context baseline generated a target-only q=1 oracle and
concluded the candidate was "retrieval-correct but not q1-exact at long
context", with every 4K-and-longer row diverging after a 67--107 token common
prefix. That teacher ran at the default `batched = 8192` with no speculative
config, so its budget fell back to 8192 and it produced its oracle on the
`8192 + 8192 + 8192 + 8064` partition, while the candidate it was judging ran
`8182 + 8182 + 8182 + 8094`.

The 2026-08-02 scheduler-alignment experiment independently measured exactly
that partition change and found it altered output token IDs on all eight long
rows, with first mismatches at zero-based indices 67 through 91. The mechanism,
the direction, and the onset window all coincide with the baseline's 67--107.

The most economical explanation is that the long-context exactness failure is an
artifact of an unmatched-partition oracle rather than a defect in the candidate.
This is inference from construction plus coinciding signatures; it is **not
proven**. Proving or refuting it costs almost nothing once a window is open:
re-derive the q=1 oracle with the teacher pinned to `batched = 8182` and
re-compare the same prompt arrays. If the rows become exact, the long-context
lane reopens and the "not q1-exact" verdict must be retracted. Until that run
exists, neither the original verdict nor this rebuttal should be cited as
settled.

## Arms

Two arms, one service each, same host, same suite, same repeat oracle, run in
this order:

1. **D11** — profile `qdepth`, `LAGUNA_LONG_DEPTH=11`, `LAGUNA_M=12`,
   `VLLM_XPU_LAGUNA_EXACT_MAX_M=12`, `max_num_batched_tokens=8192`.
2. **D7** — profile `qdepth`, `LAGUNA_LONG_DEPTH=7`, `LAGUNA_M=8`,
   `VLLM_XPU_LAGUNA_EXACT_MAX_M=8`, `max_num_batched_tokens=8188`.

Both derive budget 8182. Both hold every selector in the first table group off.
Everything else — model revisions, suite, TP4/EP4, BF16 KV, block size 64,
`max_num_seqs=1`, prefix caching off, `max_num_partial_prefills=1`, GPU
utilization, memory guards — is identical by construction, and the launcher
fails closed before `vllm serve` if any of it drifts.

## Stop rules

Frozen before any run. No retry, no guard relaxation, no post-hoc arm.

1. **Configuration.** If either arm's server log does not prove resolved
   `enable_prefix_caching=False`, `max_num_partial_prefills=1`, its declared
   batched budget, and derived budget 8182, that arm is void. Absence of proof
   is failure, not a null.
2. **Partition.** Both arms must show the same derived budget of 8182. A
   different derived budget in either arm closes the sweep.
3. **Exactness.** Every row in both arms must match the repeat oracle on prompt
   hash, output token IDs, and text hash. A single mismatch closes the sweep for
   that arm; it is not reported as a slower or faster result. This is the gate
   the 2026-08-02 alignment arm failed.
4. **Intrinsic gates.** Retrieval, cache-zero, completion-length, finish-reason,
   prefill and decode metric counts, and per-position counter consistency must
   all pass on every row, as they do today.
5. **Operational.** Any device error in the kernel journal scan, any worker
   surviving shutdown, any memory-guard stop, or any topology count other than
   the expected target capture and replay voids the affected arm. An
   operational failure is preserved and not retried, matching the disposition of
   the 2026-08-02 mixed-depth run.
6. **Decision.** D7 is reported as an improvement only if it is exact, its
   configuration is proved, and its 32,640-token decode median exceeds D11's on
   the same substrate. Any other outcome is reported as measured, including a
   regression.

## What a pass does and does not authorize

A pass authorizes exactly one thing: a written result stating the decode
difference between draft depth 11 and draft depth 7 **on the de-optimized common
substrate**, at the pinned 8182 partition.

It does not authorize:

- any claim about the incumbent q12 configuration, which neither arm runs;
- promotion, scoring, submission, or a LocalMaxxing record of any kind;
- enabling shallower drafting in the incumbent, which would require re-proving
  every width-12 selector at the new width;
- a mixed-depth source implementation, which is gated separately by
  [`2026-08-02-long-context-mixed-depth-feasibility-preregistration.md`](2026-08-02-long-context-mixed-depth-feasibility-preregistration.md)
  and its analyzer;
- any inference about depths 3, 1, or zero-draft, which this sweep does not
  measure.

One further caveat that the sweep cannot resolve. The DFlash drafter is
structurally depth-generic: its mask embedding is a single `(hidden_size,)`
vector broadcast to every masked slot, with position entering only through RoPE,
and every proposer buffer is sized from `num_speculative_tokens`. But whether
the shipped draft checkpoint was distilled for eleven-step lookahead is a
property of its weights, not of the source, and is not decidable offline.
Depth-7 acceptance may therefore differ from the first seven positions of
depth-11 acceptance for reasons that have nothing to do with cost. The
mixed-depth position histogram is the evidence that would settle it, and it is
not yet collected.

## Nothing here is promotable

No arm in this sweep is a candidate for promotion. Both arms deliberately
disable target-path optimizations that the incumbent has, so both are expected
to be **slower in absolute terms** than the measured baseline. Only the
D7-versus-D11 ratio is interpretable, and only as evidence about draft cost.

The protected `125.4619731637751 tok/s` conventional short-decode record is
untouched by this preregistration and by any run it authorizes. This sweep is a
32,640-token long-context diagnostic; it does not run, rescore, or supersede the
short-decode record, and no result from it may be compared against that number.

## Validation

Host only, in this repository:

- `serve_laguna_long_context_nvme.sh` and
  `run_laguna_long_context_baseline.sh` pass `bash -n`;
- 20 new CPU-only launcher guard tests pass. They copy the launcher beside a
  stubbed NVMe module and a recording `vllm` shim, so the real guard code runs
  with no device, model, or service. They cover both measurable depths, the
  budget pin, the refusal of depths 3 and 1, selector drift, the reserved 8202
  value, the partition-aligned teacher, and the untouched q12 profile;
- 12 new CPU-only tests pass for the resolved cache and partition prover;
- 8 new CPU-only contract tests pass binding the mixed-depth wrapper's case
  list, through the real suite and the real sentinel rule, to the row sequence
  the analyzer demands;
- the full lab suite was run before and after: **6 failed, 738 passed, 168
  subtests** beforehand and **6 failed, 778 passed, 168 subtests** afterwards.
  The same six pre-existing failures, none touched here; the passing count rises
  by exactly the 40 new cases.

## Boundary

The NVMe/device quarantine remains controlling. This note and its source
authorize no model load, service start, endpoint contact, XPU probe, benchmark,
swap change, reset, reboot, or recovery. The `qdepth` profile is inert until a
human authorizes a device window, and the 24 GiB swap layout the mixed-depth
wrapper requires is not currently established.
