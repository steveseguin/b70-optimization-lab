# 2026-07-04 - Dynamic drafter depth + placeholder reject retry no-win

## Summary

Retried the default-off dynamic drafter depth prototype after manually applying
the upstream placeholder-token rejection guard from vLLM
`7ee4d2200 [Spec Decode] Reject placeholder (-1) draft tokens in rejection sampler`.

Result: **still no-win**. The server got through startup, model readiness, and
the first strict-suite request, then failed the second request with the same XPU
indexing assert seen in the earlier partial-group attempt.

Conclusion: rejecting padded `-1` draft tokens in the sampler is not sufficient.
The Qwen/GDN XPU MTP path still does not support partial speculative groups
end-to-end. Do not retry dynamic drafter depth by only changing sampler
placeholder handling.

## Why This Was Tried

The earlier dynamic drafter depth prototype actually shortened the proposer loop
instead of only truncating accepted output after verification. That is the right
shape for reducing wasted proposer work when acceptance is low, but it creates
partial speculative groups, e.g. proposing two draft tokens while the configured
MTP width is three.

The previous attempt crashed with:

```text
/pytorch/third_party/torch-xpu-ops/src/ATen/native/xpu/sycl/Indexing.h:622:
Assertion `index >= -sizes_[i] && index < sizes_[i] && "index out of bounds"` failed.
```

Upstream vLLM recently added a placeholder-token guard for speculative sampling,
so the question was whether the old crash was just `-1` padded draft IDs being
accepted or indexed.

## Patches Preserved

- Baseline active stack before retry:
  `../../../patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-before-placeholder-reject-20260704T150900Z.patch`
- Retry patch, including the upstream-style placeholder guard and the default-off
  dynamic drafter depth prototype:
  `../../../patches/qwen36-27b-autoround-int4-b70/vllm-dynamic-drafter-depth-placeholder-reject-retry-20260704T151200Z.patch`
- Earlier partial-group crash patch:
  `../../../patches/qwen36-27b-autoround-int4-b70/vllm-dynamic-drafter-depth-partial-group-crash-20260704.patch`

The retry patch is valuable as a debugging artifact, but it should not be
promoted into the active recipe.

## Run Identity

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-dyndraft-placeholderfix-min2-low0-20260704T150827Z
```

Important identity fields from `identity.env`:

```text
gpu_index=3
port=19423
suite=repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json
bench_max_tokens=128
bench_metric_tokens=100
max_model_len=2048
max_num_batched_tokens=1024
max_num_seqs=1
enable_mtp=1
num_speculative_tokens=3
enable_xpu_graph=1
compilation_config={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}
promote_accepted_spec_state=1
nonspec_postprocess_accepted_state=0
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_DEPTH=1
VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_MIN_DEPTH=2
VLLM_XPU_SPEC_DECODE_DYNAMIC_DRAFTER_LOW_ACCEPT=0
```

## Failure

The benchmark client hit HTTP 500 during the strict suite:

```text
urllib.error.HTTPError: HTTP Error 500: Internal Server Error
```

The server log shows the underlying engine failure:

```text
/pytorch/third_party/torch-xpu-ops/src/ATen/native/xpu/sycl/Indexing.h:622:
operator(): global id: [2,0,0], local id: [2,0,0]
Assertion `index >= -sizes_[i] && index < sizes_[i] && "index out of bounds"` failed.
EngineDeadError: EngineCore encountered an issue.
```

No strict result JSON was produced, so there is no valid throughput or quality
claim and no LocalMaxxing submission.

## Interpretation

The placeholder reject guard is useful, but this crash happens below the simple
sampler-acceptance layer. Likely remaining incompatible surfaces for partial
groups include one or more of:

- verifier logits row selection still assuming configured MTP width;
- GDN/Mamba state promotion or rollback assuming a fixed speculative width;
- draft/target metadata shapes using full-width graph captures while the
  current request carries fewer draft rows;
- bonus-token and accepted-count plumbing assuming the full configured width.

Because the failure survived the upstream placeholder guard, dynamic drafter
depth should stay closed until the partial-group contract is made explicit
across proposer output, verifier metadata, sampler rows, GDN state commit, and
graph capture shapes.

## Next Useful Follow-Up

If this lane is reopened, do not start with another full strict run. Start with
a tiny crash-localization probe and sync/debug stages:

- `VLLM_XPU_SYNC_DEBUG_STAGES=*` or targeted stages around logits selection,
  sampling, accepted-count write, and GDN commit;
- `VLLM_XPU_REJECTION_SYNC_DEBUG_STAGES=*` around rejection sampler logits
  indexing and kernel launch;
- `VLLM_XPU_SAFE_SPEC_LOGITS_SELECT=1` if testing whether the failure is an XPU
  advanced-indexing issue.

Only after the exact stage is isolated should a new patch be attempted.

## Status

Closed as **no-win / blocked by partial-group support**.

Keep the current promoted recipe unchanged:

- webhie/Qwen3.6-27B-int4-AutoRound;
- runtime INT8 LM-head with BF16 scales;
- MTP3;
- `max_cudagraph_capture_size=8`;
- current strict fresh record `65.27648650325429 tok/s`.
