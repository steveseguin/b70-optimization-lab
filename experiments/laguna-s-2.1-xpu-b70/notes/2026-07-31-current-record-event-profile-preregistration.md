# Laguna 122.829 record current-stream event-profile preregistration

Date: 2026-07-31 America/Toronto

Status: **scoped target diagnostic passed; graph work remains dominant but is
distributed across all three per-layer graph slots; no benchmark, endpoint,
or submission claim is authorized from the perturbed profile**.

## Purpose

The transposed-scale record is conventionally `122.828558121099 tok/s`, while
the requested frontier is 130. Historical cycle attribution predates width 12,
the current DFlash graph stack, GRF128 target decode, and contiguous target
scales. It is no longer an adequate basis for selecting the next candidate.

Run the existing default-off current-XPU-stream event profiler on the exact
record stack. It places timing events around the already audited target replay
callbacks and changes no tensor, operation, callback order, graph segment,
collective, attention call, model precision, or arithmetic.

## Frozen execution

- vLLM: `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU kernels: `8dd94f2307db3b830fe07f212c4b36f719652a5c`;
- grouped-GEMM SHA-256:
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- BF16 KV, width 12 / depth 11, one active generation;
- target topology 146 graphs / 145 eager breaks per rank;
- draft topology 14 / 13 per rank;
- fixed cold 13-prompt suite, no warmup, no retry, cache-zero required;
- exact target-q1 token and text comparison remains mandatory;
- runtime lock:
  `experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-transposed-scales.json`.

The diagnostic uses exactly one fresh measurement-leg process with a new
owner-private event root. Because event synchronization intentionally perturbs
one verifier replay, any rate emitted by the surrounding harness is invalid
and must not be quoted, promoted, compared, or submitted.

## Interpretation

Require four complete rank files, 146/145 topology, identical segment-kind
order, exact/cache-zero suite completion, clean teardown, and post-run idle.
Select only one real rank's internally consistent total and category sums; do
not combine per-category maxima from different ranks.

This profiler observes the first audited replay and may include cold replay or
frequency effects. XCCL may use an internal stream, so collective completion is
not a validated global critical path. Results are directional candidate
selection only:

- graph-dominated: inspect repeated layer graph positions and target grouped
  GEMM/device-kernel work;
- attention-dominated: revisit only exact attention execution, not KV dtype;
- collective-dominated: require completion-join proof before changing any
  boundary or topology;
- no material concentration: stop micro-tuning this replay wrapper and profile
  the draft/current full cycle separately.

No reset, reboot, privileged recovery, source mutation, endpoint claim, or
LocalMaxxing submission is authorized by this diagnostic.

## First execution: classified pre-profile stop

Run root:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-current-record-event-profile-20260801T0310Z`

Empty event root:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-current-record-event-profile-data-20260801T0310Z`

The service passed record identity and model initialization, but the first
request returned HTTP 500 on all ranks with:

`RuntimeError: Laguna XPU event-profile segment topology drift`

The event-profile environment currently applies to every Breakable wrapper.
The current record has both the 14/13 segmented DFlash wrapper and the 146/145
target wrapper. DFlash runs first, claimed the process-global one-shot profile,
and correctly failed the historical hard-coded target-topology check. No rank
file was written, no profiled replay completed, and there is no timing,
correctness, or performance result. Formal cleanup reported stop/worker/idle
status zero, all GPUs returned idle, and no reset or reboot occurred.

## Scoped diagnostic amendment

One default-off diagnostic-only vLLM change is authorized in a separate
worktree: add a fail-closed literal target-only scope for this existing event
profiler. When enabled, a Breakable wrapper whose captured segment kinds do not
match the exact 146 graph / 97 collective / 48 attention target topology must
bypass profiling and replay normally without claiming the process-global
one-shot. The matching target wrapper must retain every existing digest,
stream, event-count, file, rank, and topology check.

Requirements before another model action:

1. existing behavior is byte-for-byte source-default when the new variable is
   unset or zero;
2. only literal zero/one is accepted;
3. a 14/13 draft-like fixture bypasses profiling and cannot claim/write;
4. a 146/145 target fixture still profiles and writes exactly once;
5. invalid and no-matching-topology cases remain fail-closed at the outer
   diagnostic gate;
6. focused Breakable-graph tests, formatting, and diff checks pass;
7. commit the exact source and record its identity before one fresh rerun.

This amendment changes diagnostic selection only. It does not authorize any
ordinary runtime treatment, score, retry after a second failure, reset,
reboot, or submission.

## Amendment implementation

The scoped diagnostic source is committed cleanly at:

- worktree: `/home/steve/src/laguna-vllm-target-only-event-profile-20260731`;
- vLLM commit: `50bf5df198d8835f6b59725cbf5cc31da666f814`;
- commit subject: `xpu: scope Laguna event profile to target replay`.

It adds the default-off literal environment variable
`VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_TARGET_ONLY`. Literal one makes the
14/13 draft wrapper replay normally without claiming the process-global
profile and selects only the exact existing 146/145 target topology. Unset or
literal zero follows the previous code path. Invalid values fail closed.

Validation on that exact source commit:

- full Breakable-graph test file: 44 passed, 11 platform skips;
- focused XPU event-profile cases: 20 passed;
- formatting, lint, and diff checks passed;
- draft bypass, process-global claim preservation, exact-target selection,
  and invalid-literal behavior have dedicated tests.

The measurement leg now accepts this selector only as optional argument 36,
records it in identity, verifies it in the captured service environment, and
requires an event-profile root when enabled. Any nonempty event-profile root
forces `scored_measurement=0` in identity, independently of the resulting
throughput fields. The default record invocation remains argument-compatible
and passes literal zero to the service.

## Scoped execution result

The one authorized rerun passed the complete diagnostic gate:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-current-record-target-event-profile-20260801T023248Z

/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-current-record-target-event-data-20260801T023248Z
```

- identity records `scored_measurement=0`, target-only profiling literal one,
  vLLM `50bf5df198d8835f6b59725cbf5cc31da666f814`, and kernel
  `8dd94f2307db3b830fe07f212c4b36f719652a5c`;
- draft capture/replay was exactly 14/13 on all four ranks;
- target capture/replay was exactly 146/145 on all four ranks;
- four complete rank files contain the same 291-kind order and digest
  `e5b64443ef499d8bb8b138a94ad504effeaa6434a8884ae9f885aecf12d34e1b`;
- the frozen suite was 13/13 token and text exact, all cached-token counts were
  zero, and the rollover/cross-request gates passed;
- formal cleanup reports original, stop, worker, and idle status zero. No
  reset or reboot occurred.

The diagnostic rate is intentionally discarded. On the slowest internally
consistent rank (rank 2), the profiled first target replay was 130.573 ms:

| interval kind | count | sum | share | median |
| --- | ---: | ---: | ---: | ---: |
| graph | 146 | 91.200 ms | 69.8% | 622.34 us |
| collective | 97 | 28.141 ms | 21.6% | 297.23 us |
| attention | 48 | 11.232 ms | 8.6% | 216.27 us |

All four ranks agree on the ordering: graph 64.9--69.8%, collective
21.6--26.7%, and attention 8.3--8.9%. These reproduce the older directional
ordering on the current 122.829 stack rather than relying on the former
100-tok/s runtime.

The repeated six-interval layer pattern further splits rank 2's graph sum:

| graph slot | source-level contents | 48-layer sum |
| --- | --- | ---: |
| before attention | input norm, fused QKV, Q/K norm and RoPE | 28.645 ms |
| after attention | gate, gated attention, output projection | 27.442 ms |
| after output collective | post-attention norm and target MoE | 34.028 ms |

The source-level labels are derived from the fixed decoder order around the
attention and collective boundaries. They are not per-kernel timing labels.
The result therefore says that captured device work remains the correct class
to optimize, but it does not support treating the already heavily optimized
MoE slot as the only remaining graph cost.

As preregistered, event synchronization makes the absolute 130.573 ms
non-representative, the first replay may contain cold effects, and XCCL
cross-stream completion is not validated. Do not convert these shares into a
throughput projection or combine category maxima from different ranks.
