# 2026-07-06 - Native prefix-base target-tail recovery is no-win

## Context

This follows `2026-07-06-native-prefix-base-extra-block-partial.md`. The fast
native prefix-base lane reached `70.15392515866824 tok/s` on the strict fresh
suite, but failed repeat64 with intermittent truncation (`blue, green, red`).
The trace pointed at a partial-reject row where the target-owned replacement
was emitted as visible output while the GDN/Mamba state transaction only had an
accepted draft-prefix state.

A subagent audit confirmed the smallest source hook was in
`vllm/v1/core/sched/scheduler.py`, where scheduler-visible output accounting is
separate from the runner's GDN/Mamba accepted-count path. The hypothesis was:
keep the target-owned replacement/bonus visible, but rewind computed-token
accounting by one extra token and force the next step to consume that tail as a
normal one-token decode before another packed verifier row.

## Patch

Preserved patch snapshot:

`patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-native-prefix-target-tail-recovery-20260706.patch`

New default-off gate:

```text
VLLM_XPU_GDN_NATIVE_SPEC_TARGET_TAIL_RECOVERY=1
```

The tested run also used the prior replacement-prefix state count correction:

```text
VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1
VLLM_XPU_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS=1
VLLM_XPU_GDN_NATIVE_SPEC_TARGET_TAIL_RECOVERY=1
```

The first implementation crashed in the trace path because the new trace fields
were passed to `_trace_spec_decode_step()` without extending its explicit
signature. After fixing that, the second implementation crashed async scheduler
placeholder accounting (`num_output_placeholders < 0`). A third implementation
added one temporary async placeholder when rolling the target tail back as
uncomputed; that reached the strict and quality gates.

Crash summaries for the first two attempts are preserved as:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-tailrecovery-replcounts-20260706T142650-candidate-summary-20260706T142650Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-tailrecovery-replcounts-v2-20260706T142901-candidate-summary-20260706T142901Z.json`.

## Validated candidate

Label:
`qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115-candidate-summary-20260706T143115Z.json`
- strict fresh benchmark:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115-realistic128-chat-tokenids-qwensuite-20260706T143115Z.json`
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115-repeat64-ctx1024-20260706T143115Z.json`
- smoke:
  `data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115-20260706T143115Z.json`
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-prefixbase-tailrecovery-replcounts-v3-20260706T143115-20260706T143115Z`

Identity:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`, revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 GPU, TP1, MTP3, strict fresh realistic suite;
- target runtime INT8 LM-head with BF16 scales;
- draft runtime INT4 LM-head, group size 128, BF16 scales;
- XPU graph `PIECEWISE`, `max_cudagraph_capture_size=8`;
- native prefix-base GDN + replacement-prefix counts + target-tail recovery.

Result:

- strict fresh gate: pass (`cached_tokens=0` on all 12 prompts, each prompt run
  once);
- median tokens 1-100 after TTFT: `32.800204139744004 tok/s`;
- p10: `24.587922249226978`;
- mean: `31.73548646320224`;
- median TTFT: `603.2414470100775 ms`;
- quality: fail.

Quality failures:

- `copy_phrase`: emitted `satin` instead of `satin cobalt orbit`;
- `json_schema`: emitted malformed `{"answer": 42, "unit be, "unit": "`;
- long-context gate did not pass;
- baseline match failed.

## Interpretation

The target-tail recovery hypothesis is closed as implemented. It did not only
cost throughput; it corrupted exact short outputs. The likely reason is that
making a visible target-owned token uncomputed after the scheduler has already
streamed it creates a mismatch among async output placeholders, request visible
token history, KV/GDN state, and the next packed verifier boundary. Even with
placeholder compensation, the transaction is not equivalent to canonical
single-token decode.

Do not repeat this scheduler wrapper path. The remaining credible native
prefix-base fix would have to be lower-level: a graph-safe GDN/DeltaNet
transaction that processes the target-owned replacement/bonus state without
rewinding visible scheduler output, or a fundamentally different proposer path
that avoids the target-owned replacement boundary.

For near-term Qwen27 speed work, pivot away from wrapper recovery and back to
higher-value attack surfaces: verifier/LM-head waste, stronger acceptance, or
native kernels that preserve exact target verification without disturbing
scheduler-visible token history.
