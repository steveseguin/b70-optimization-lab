# Laguna production concurrency audit: which selectors survive batch > 1

Date: 2026-08-03 America/Toronto

Status: **static source audit and fail-closed launcher implemented and
CPU-tested; no service, model, endpoint, XPU, benchmark, or performance run was
performed**. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched and no new rate is claimed anywhere in this note.

## The question

Every measured record in this campaign was produced at `--max-num-seqs 1`. The
open product question is whether the same stack can serve concurrent traffic,
or whether production must run single-stream. The prior working claim was that
"concurrency disables everything", which was too strong to act on and had not
been checked selector by selector. This note settles it from source.

## First correction: there are not 84 selectors

`grep -c VLLM_XPU_LAGUNA_ vllm/envs.py` returns 84, but that is a count of
occurrences, not of selectors. The true universe is:

- **28** distinct `VLLM_XPU_LAGUNA_*` names declared in `vllm/envs.py`;
- **31** distinct `VLLM_XPU_*` names declared there in total;
- **54** distinct `VLLM_XPU_LAGUNA_*` names across the vLLM fork and the XPU
  kernels repo combined, of which 15 are diagnostic instrumentation that never
  belonged in a serving profile.

The audit below covers all 54, plus the six non-`LAGUNA` `VLLM_XPU_*` selectors
that carry batch consequences.

## Second correction: there are six batch validators, not four

The four named in the original framing are real, but two more exist:

| Site | Term |
|---|---|
| `gpu_model_runner.py:4195` | `_validate_laguna_m8_breakable_graph_config` |
| `gpu_model_runner.py:4295` | `_validate_laguna_m8_evidence_config` |
| `gpu_model_runner.py:4337` | `_validate_laguna_exact_prefill_chunks_config` |
| `gpu_model_runner.py:4380` | `_validate_laguna_wide_prefill_qknorm_rope_config` |
| **`gpu_model_runner.py:729-730`** | **`persistent K-step decode requires max_num_seqs=1`** |
| **`laguna.py:179-182`** | **`(scheduler_config.max_num_seqs == 1, "max_num_seqs is not 1")`** |

The last one matters most. It sits in
`_laguna_m8_shared_elementwise_contract_violations` and raises from
`laguna.py:706-719` whenever `M8_SHARED_ELEMENTWISE` or `M12_SHARED_ELEMENTWISE`
is on. Because the record profile enables `M12_SHARED_ELEMENTWISE`, **the sealed
stack cannot silently start at batch > 1 — it aborts during model
construction.** That is the single most reassuring finding here.

There is also a seventh, independent copy of the K-step guard in
`vllm/v1/core/sched/scheduler.py:237-259`, which adds two constraints the runner
copy lacks (prefix caching disabled, PP=1).

## The finding that actually decides the question

The batch hostility is worse than "the optimizations turn off". At batch > 1
with the exact stack enabled, the model does not disable the exact path — it
takes a **silent per-row serialization** that is slower than plain batched
execution would have been.

`laguna.py:848-859` computes two gates from the flattened row count:

```python
batched_exact_rows = (... and 1 <= hidden_states.shape[0] <= xpu_laguna_exact_max_m() ...)
exact_spec_rows = (
    os.environ.get("VLLM_XPU_EXACT_SPEC_ATTN") == "1"
    and self.exact_spec_target
    and 1 < hidden_states.shape[0] <= 512
    and not batched_exact_rows
)
```

At batch 1 with DFlash depth 11 the decode row count is exactly 12, so
`batched_exact_rows` is true. At batch N it is `12*N`. At N=2 that is 24, which
exceeds `EXACT_MAX_M`, so `batched_exact_rows` goes false and `exact_spec_rows`
goes **true** (24 <= 512). Control then reaches `laguna.py:892-898`:

```python
final_hidden_states = torch.cat(
    [
        self._forward_flat(hidden_states[row : row + 1])
        for row in range(hidden_states.shape[0])
    ],
    dim=0,
)
```

That is 24 sequential single-row MoE forwards per layer, each with its own
router GEMM, grouped GEMM pair and TP collective. The same shape of fallback
exists in `linear.py:762-771` (`ColumnParallelLinear`) and `linear.py:1944+`
(`RowParallelLinear`), one launch and one all-gather per row. No log, no
warning, no exception.

`VLLM_XPU_EXACT_SPEC_ATTN` is the master switch for all of it, and it is the
one selector with **no `max_num_seqs` guard anywhere in either repo**. It does
not fail closed. It degrades. The window `1 < rows <= 512` holds for every
batch size up to N=42, so there is no batch size at which the stack "escapes"
into a sane path — it stays in the per-row loop across the whole reachable
range.

`EXACT_MAX_M` cannot be raised to compensate: `linear.py:111-121` hard-clamps
it to `1..16`, so N=2 at depth 11 is already out of range by construction.

## Classification table

Legend: **H** BATCH-HOSTILE, **S** BATCH-SAFE, **U** UNKNOWN, **D** diagnostic
only (never a production selector). "Miss" is what happens when the gate is not
satisfied: *raise* is loud and safe to operate against; *silent* is the class
that yields uninterpretable measurements.

### BATCH-HOSTILE — 28 of 54

| Selector | Batch or row gate | Miss |
|---|---|---|
| `BATCHED_EXACT_MOE` | `1 <= rows <= EXACT_MAX_M` | **silent** per-row loop |
| `EXACT_MAX_M` | `rows == EXACT_MAX_M`, `num_reqs != 1` | raise at boot / **silent** per step |
| `EXACT_PREFILL_CHUNKS` | validator `max_num_reqs != 1`; step `num_reqs != 1` | raise at boot / silent step |
| `WIDE_PREFILL_QKNORM_ROPE` | validator `max_num_reqs != 1`; rows in {1024, 4096, 8094, 8182} | raise at boot / **silent** |
| `M8_BREAKABLE_GRAPH` | validator `max_num_reqs != 1`; `capture_sizes == [12]` | raise at boot / **silent** `force_eager` |
| `M8_CAPTURE_ATTENTION_GRAPHS` | requires breakable graph | raise |
| `M8_PREBUILT_EXACT_ATTN_METADATA` | `query_start_loc.numel() != 2`, `block_table.shape[0] != 1` | raise / silent eligibility |
| `M8_PERSISTENT_KV_CACHE_VIEWS` | none in its own body; hostile only via required deps | raise |
| `DFLASH_SEGMENTED_GRAPH` | `num_input_tokens == 12` | **silent** |
| `DFLASH_CAPTURE_ATTENTION_GRAPHS` | inherits segmented | **silent** |
| `DFLASH_INLINE_ATTENTION_GRAPHS` | inherits segmented | **silent** |
| `DFLASH_CONTEXT_KV_WORKSPACE` | `"batch": max_num_seqs != 1`; runtime `0 < num_ctx <= 12` | raise at boot / **silent** runtime |
| `DFLASH_FP8_W8A16` | inherits the context-KV contract; `1 <= rows <= 12` | raise both |
| `M8_QKNORM_ROPE` | `rows in (8, 12)` | **silent** |
| `M8_SHARED_ELEMENTWISE` | `max_num_seqs == 1`; `rows == 8` | raise at boot / **silent** step |
| `M12_SHARED_ELEMENTWISE` | `max_num_seqs == 1`; `rows == 12` | raise at boot / **silent** step |
| `M12_MAPPED_GATHER_SCALE_ADD` | `shape == (12, 3072)`; kernel `kNumTokens = 12` | **silent** |
| `M8_BF16_ROUTER_TOPK` | `rows == 8`; logits shape in `((8,256),(12,256))` | **silent** `.float()` |
| `MWIDE_BF16_ROUTER_TOPK` | `rows == 12`; `capture_sizes == [12]` | raise at boot / **silent** step |
| `M8_REMOTE_ZERO` | `1 <= num_rows <= 8` | **silent**, no else |
| `M8_FUSED_TRANSACTION` | `1 <= num_rows <= 8` | **silent**, no else |
| `M8_FUSED_W1_ROUTE_W2` | `max_num_seqs == 1`; `1 <= num_rows <= 8` | raise at boot / **silent** |
| `M8_BF16_ATTN_MM` | `rows == 8` | **silent** stride-zero bmm |
| `M8_ROUTE_INTERLEAVE` | co-located with `max_num_seqs == 1`; `num_rows == 8` | raise at boot / **silent** |
| `M8_GATHER_FINALIZE` | `num_rows == 8`; kernel `kNumTokens = 8` | raise one way / **silent** other |
| `DECODE_GRF128` | `total_m == 120` | **silent** revert to 256-GRF |
| `DECODE_EXACT_SPECIALIZED` | downstream of GRF128 | **silent** |
| `DECODE_TRANSPOSED_SCALES` | `total_m == 120`, host `num_rows == 12` | **silent**, tripwire cannot fire |

### BATCH-SAFE — 8 of 54

| Selector | Why it survives |
|---|---|
| `INT4_TILE_RECORD` | load-time weight-layout contract only; no row term; raises on drift |
| `SCALE_VEC` | runtime bool, applied identically at every M |
| `SCALE_FOLD` | runtime bool; off in the record |
| `DEQUANT_MAD` | runtime bool; off in the record |
| `REPLICATED_EMBEDDING` | `F.embedding` on a replicated table; no batch or row term anywhere |
| `DETERMINISTIC_GRAPH` | no batch term — but see the inert list below |
| `DRAFT_BREAKABLE_GRAPH` | no row term; the record requires it OFF, so safe vacuously |
| `M8_W1_N_TILE` (value 64) | 64 has no row predicate; 32 and 128 are gated on `num_rows == 8` |

`SCALE_VEC` deserves a note: it is the only member of the INT4 decode bundle
that keeps working when the `total_m == 120` gate misses. `GRF128` requires
`SCALE_VEC`, but not the reverse.

### UNKNOWN — 3 of 54

| Selector | Why source cannot decide | Deciding measurement |
|---|---|---|
| `DECODE_NO_KLOOP_BARRIERS` | no consumer exists in either repo; the only references are the worker evidence string list | A/B the record config with it at `1` vs `0` (evidence contract unset so `0` is accepted) and compare decode latency and emitted-token identity. Identical results prove it inert. Sibling branch `laguna-xpu-kernels-m12-kloop-barrier-20260801` may hold the implementation. |
| `SCALE_LANE_DEDUP` | same: evidence-string only, no `getenv`, no consumer | same A/B; sibling branch `laguna-xpu-kernels-scale-lane-dedup-20260801` |
| `PREFETCH_DIST` | validated and stored, but `laguna_int4_prefetch_dist()` is called only from the three M8Topk launchers, which are reachable only via `1 <= num_rows <= 8`. The generic grouped GEMM that runs the 12-row decode takes the compile-time default 6. | A/B `PREFETCH_DIST=3` vs `=12` at exactly 12 rows. Bit-identical and time-identical output proves it inert on the record path. |

### Diagnostic only — 15 of 54

`M8_EVIDENCE`, `M8_EVIDENCE_ARM`, `M8_EVIDENCE_ROOT`, `DRAFT_IDENTITY_PROBE`,
`PARITY_PROBE`, `PARITY_RETURN_STAGE`, `CYCLE_ATTRIBUTION_ROOT`,
`CYCLE_ATTRIBUTION_DEVICE_CYCLES`, `CYCLE_ATTRIBUTION_TOPK_PROBE`,
`REPLAY_PROFILE_ROOT`, `REPLAY_PROFILE_SAMPLES`, `REPLAY_EVENT_PROFILE_ROOT`,
`REPLAY_TRACE_SESSION`, `REPLAY_TRACE_UNITRACE`, `REPLAY_TRACE_UNITRACE_SHA256`.

None are performance selectors. Five transitively pin `max_num_seqs=1` through
`M8_BREAKABLE_GRAPH`. Most write files under a mode-`0700` root and add
synchronous host work to the serving path. Two are worse than slow:

- `DRAFT_IDENTITY_PROBE` logs raw token ids at INFO, leaking user content.
- **`PARITY_RETURN_STAGE` produces incorrect output, not slow output.** It
  `break`s out of the decoder-layer loop and returns a partial hidden state
  (`laguna.py:1703-1722`). Treat it as a landmine.

### Non-`LAGUNA` selectors with batch consequences

| Selector | Class | Note |
|---|---|---|
| `VLLM_XPU_EXACT_SPEC_ATTN` | **H** | the master exactness switch; no `max_num_seqs` guard anywhere; **silent** per-row serialization |
| `VLLM_XPU_PERSISTENT_KSTEP_DECODE` | **H** | two independent raises; also mutually exclusive with any speculative config, so it can never coexist with DFlash |
| `VLLM_XPU_NATIVE_K2_SINGLE_SUBMISSION` | **H** | requires K-step decode = 2, hence batch 1 |
| `VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX` | **S** | companion requirement only |
| `VLLM_XPU_ENABLE_XPU_GRAPH` | **S** | graph enable |
| `VLLM_XPU_USE_SAMPLER_KERNEL` | **S** | default on |

## Selectors that are already inert at the record width

This is a side finding, but it bears on how the record should be described. The
verifier width moved 8 -> 12, and several `<= 8` or `== 8` bounds did not move
with it. At the incumbent 12-row decode these are **already** not firing at
batch 1:

- `DETERMINISTIC_GRAPH` — all three of its exact paths are gated `<= 8` rows,
  while `skip_compiled` is permanently true above 8 tokens. Its only live effect
  at width 12 is to disable compiled execution.
- `vllm/model_executor/layers/logits_processor.py:148-152` — hardcoded
  `1 <= hidden_states.shape[0] <= 8`, not `EXACT_MAX_M`. (Coordinator verified;
  note the path is `model_executor/layers/`, not `v1/sample/`.)
- Kernels `fused_moe_interface.py:1320` — `1 <= num_rows <= 8`, so the named
  batched-exact MoE device path is not entered at 12 rows; the M12 effect
  arrives through `m12_mapped_tail_call` instead.
- `M8_REMOTE_ZERO`, `M8_FUSED_TRANSACTION`, `M8_GATHER_FINALIZE`,
  `M8_BF16_ATTN_MM` — all inside 8-row windows.
- `PREFETCH_DIST` — see UNKNOWN above.

None of this changes the measured record, which is a whole-system number. It
does mean that per-selector attribution at width 12 should not be assumed from
the selector's name, and that the `qdepth` note's caution about width
independence was well placed.

## The two production profiles

### Profile A: sealed single-stream (recommended)

The record identity, unchanged: `--max-num-seqs 1`, `max_model_len 32768`,
`EXACT_MAX_M=12`, `LAGUNA_SPEC=11`, DFlash segmented graph, context-KV
workspace, FP8 W8A16 draft, M12 shared elementwise, exact BF16 router, GRF128
and transposed scales.

- **What is lost relative to the record:** nothing. This is the record.
- **What is unmeasured:** nothing new. It is the configuration whose decode
  rate is `125.4619731637751 tok/s` conventional.
- **Cost:** no queuing. A second concurrent request waits. On this host that
  matters less than it sounds, because the memory ceiling below caps real
  concurrency at 2 full-length requests anyway.

### Profile B: concurrent-capable

`--max-num-seqs >= 2`, every BATCH-HOSTILE selector explicitly off, nothing
UNKNOWN enabled, `--enforce-eager`, no speculative config.

- **Retained:** `INT4_TILE_RECORD`, `SCALE_VEC`, `SCALE_FOLD`, `DEQUANT_MAD`,
  `REPLICATED_EMBEDDING`, `M8_W1_N_TILE=64`. That is the INT4 weight-layout and
  scale-handling work, and the embedding all-gather removal.
- **What is lost:** the entire exact/M12 fusion stack, the DFlash speculative
  path, the segmented graph, GRF128 and transposed scales. In practice that is
  every optimization the campaign has been measuring for weeks.
- **What is unmeasured:** its decode rate, at any batch size. No arm has ever
  run `VLLM_XPU_EXACT_SPEC_ATTN=0` on this stack. The profile is therefore a
  configuration that is *known to be executable and known not to silently
  degrade*, not a configuration with a known throughput.

Speculation is refused in Profile B rather than left to an operator. DFlash at
batch > 1 is only reachable with `EXACT_SPEC_ATTN=0`, which no arm has run;
enabling it would produce an uninterpretable result rather than a fast one.

## The physical ceiling

Concurrency here is bounded by memory, not by software.

| Utilization | KV tokens | Full 32,640-token requests | Outcome |
|---|---|---|---|
| 0.70 | none allocatable | 0 | clean exit, `-0.14 GiB` available KV |
| 0.75 | — | — | stopped at the host-memory guard |
| **0.80** | **91,258 - 109,059** | **2.78 - 3.33** | sufficient; retained identity |
| 0.90 | 224,081 | ~6.84 | **exhausted host swap and took the host down** |

The launcher uses the measured **floor** of 91,258, not the ceiling, because a
launcher may not assume it drew the lucky allocation. At 32,768 tokens per
request that is **2 concurrent full-length requests**, and the third is refused
by arithmetic with the numbers shown. Shorter `max_model_len` buys more: 8,192
tokens per request admits 8.

The swap hazard is made unreachable rather than documented: utilization above
0.80 is refused unconditionally with no override, and a pre-launch host-memory
check reproduces the calibrated guard — stop below 12 GiB available RAM, or
when free swap is below 4 GiB *and* available RAM is below 16 GiB.

## Network exposure

vLLM's OpenAI-compatible endpoint is unauthenticated unless an API key is
supplied, and it terminates plain HTTP. This host is LAN-facing.

The launcher binds `127.0.0.1` by default and refuses any other bind unless the
operator both acknowledges it and supplies an API key from a mode-600 or -400
absolute path holding at least 32 characters, which is then passed as
`--api-key`.

**Explicitly out of scope, with reasoning:** TLS, rate limiting, per-user
identity, quota, and audit are not implemented here. A single shared bearer
token is an access gate, not an authorization system. The campaign already has
the right posture for this — the production readiness canary keeps the backend
loopback-only and has an orchestrator expose a separate frontdoor after
`production-ready.json` is published. The launcher's job is to make the unsafe
default impossible, not to become the frontdoor.

## Recommendation

**Run production single-stream.** The reasoning is not "concurrency is hard";
it is that on this host concurrency buys at most 2 full-length requests while
costing every optimization the campaign has measured, and 13 of the 28 hostile
selectors have **no loud guard at all** — they simply stop firing. Those 13 are
`BATCHED_EXACT_MOE`, `DFLASH_SEGMENTED_GRAPH`,
`DFLASH_CAPTURE_ATTENTION_GRAPHS`, `DFLASH_INLINE_ATTENTION_GRAPHS`,
`M8_QKNORM_ROPE`, `M12_MAPPED_GATHER_SCALE_ADD`, `M8_BF16_ROUTER_TOPK`,
`M8_REMOTE_ZERO`, `M8_FUSED_TRANSACTION`, `M8_BF16_ATTN_MM`, `DECODE_GRF128`,
`DECODE_EXACT_SPECIALIZED`, and `DECODE_TRANSPOSED_SCALES`. The sealed profile
is saved only because `M12_SHARED_ELEMENTWISE` happens to raise; a partial
profile assembled without it would boot, serve correct tokens, and be quietly
slow.
A queue in front of a 125 tok/s single-stream service is a better product than
an unmeasured concurrent service that is quietly slower per request.

If concurrency becomes a hard product requirement, the honest path is to
measure Profile B first and treat it as a new baseline, not as a degraded
record — and to measure it at `max_model_len` well below 32,768, where the
memory ceiling actually permits useful batching.

## Implementation

- `tools/serve_laguna_production.sh` — production launcher, distinct from every
  cold benchmark launcher. Validates its own selector set, refuses contradictory
  combinations by name with the reason, refuses any BATCH-HOSTILE selector
  alongside `max_num_seqs > 1`, enforces the KV and host-memory ceilings, and
  defaults to a loopback bind. It does not modify, and is not modified by,
  `serve_laguna_long_context_nvme.sh`.
- `tools/test_serve_laguna_production.py` — host-only guard tests using the
  established technique: the launcher is copied beside a stubbed NVMe module, a
  recording `vllm` shim, and a synthetic `meminfo`. The swap hazard is tested
  against the synthetic file, so the guard is exercised without ever creating
  the condition.

## Offline validation

- 53 new production-launcher guard tests pass.
- Full lab tool suite: **4 failed, 833 passed, 168 subtests passed** on
  `/home/steve/.venvs/deepseek-v4-xpu/bin/python`. The 4 failures are the known
  pre-existing baseline failures (`test_freeze_laguna_m8_gather_sharded_stage0_completion`,
  `test_laguna_exact_small_postrecovery`, and two in
  `test_laguna_m8_gather_finalize_component`, the latter two on native identity
  drift of `installed/_moe_C.abi3.so`). No new failure was introduced.
- Ruff check and format clean for the new Python file.
- `bash -n` clean for the new launcher. `shellcheck` is not installed on this
  host, so no shellcheck result is claimed.

## Boundaries

Nothing was run. No model was loaded, no vLLM service started, no inference
endpoint contacted, no XPU or `torch.xpu` call made, no benchmark or gate
executed. Nothing under `/mnt/fast-ai` was read or written. No execution lock,
runtime lock, evidence packet, or frozen manifest was modified, refreshed, or
regenerated. No `sudo`, reboot, reset, driver reload, or swap change was
performed. The corrected-error PCIe/NVMe quarantine remains controlling and
this work grants no authorization to relax it.

Every classification here is derived from source. The two profiles are
configurations, not results. The protected conventional short-decode record
remains `125.4619731637751 tok/s`, measured at `--max-num-seqs 1`, and is
untouched by this work.
