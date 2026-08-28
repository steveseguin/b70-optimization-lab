# Qwen3.8 FP8 TP2 MTP1: deterministic compiled result

## Promoted result

The official-FP8/W8A16 TP2 MTP1 lane is now strictly qualified at
**51.918757 tok/s**. Two independent fresh servers, each using an empty compile
cache, ran the complete fixed 12-prompt/six-class suite with a natural
512-token cap. Every request reported `cached_tokens=0`; both workload gates
and independent canary batteries passed; all complete token arrays matched
between attempts and against both qualified compiled MTP0 r15 target repeats.

| attempt | class-balanced decode | repeat parity | target parity |
| --- | ---: | ---: | ---: |
| r32 A | 51.606902 tok/s | 12/12 | 12/12 vs r15 A and B |
| r32 B | 52.230611 tok/s | 12/12 | 12/12 vs r15 A and B |
| two-attempt median | **51.918757 tok/s** | **qualified** | **qualified** |

The matched MTP0 control is 34.031596 tok/s, so MTP1 improves strict decode by
**52.56%** without changing the complete greedy output arrays.

## Fix

Qwen3.8 MTP1 packs the target token and one speculative verifier token into a
two-row `GemmaRMSNorm` call. The existing native XPU reduction can produce a
different first row for the packed call than for the target-only one-row call.
The repository patch replays exactly those two packed rows through the original
one-row native operator while leaving every one-row target invocation
untouched. A 100-trial operator proof covers plain, fused-add, and residual
outputs and reports zero mismatches and zero maximum absolute difference.

Fresh compiler scheduling was a second source of instability. The patched
image without `TORCHINDUCTOR_DETERMINISTIC=1` produced a clean 52.189205 tok/s
attempt but matched only 9/12 target arrays. Enabling deterministic Inductor,
with every other setting fixed, produced the qualified r32 A/B pair above.

The validated image is
`neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31`, image ID
`sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`.
It overlays only the RMSNorm integration file onto the already-qualified r15
MTP0 image and retains XPU kernels `1e90ffa672`.

## Why earlier fast observations remain rejected

This closure does not rehabilitate selected fixtures or failed repeats:

- r23 showed that disabling W8A16 did not repair MTP parity;
- r24/r25 established a matched eager RMS-only path, but it was slower than
  the compiled MTP0 public baseline;
- r26 attempted an eager draft with a compiled target, but the required RMS
  marker did not fire because compiled `CustomOp` dispatch bypassed the first
  XPU-only branch. It stopped at preflight and produced no benchmark claim;
- r28 made compiled MTP1 match a patched MTP0, but that patched target itself
  matched qualified r15 on only 6/12 prompts and was rejected;
- r29 expressed a generic per-row serial RMS loop, but symbolic unrolling
  stalled compilation before inference. The bounded two-row r30 patch replaced
  it rather than treating the stalled attempt as evidence;
- r30 A matched r15 at about 52.18 tok/s, but its fresh-cache B repeat matched
  only 6/12. A alone was a false positive and was never promoted;
- r31 removed the earlier serial-GDN diagnostic overlay and still matched only
  9/12, proving that overlay was not the remaining cause;
- the old 40-token high-acceptance fixture and 128-token dynamic screen remain
  diagnostics, not strict headlines.

The earlier r19-r22 note also carries an audit correction: those candidates
changed the global batch-invariant setting relative to their target oracle, so
their causal localization claims were withdrawn even though the candidates
were correctly withheld.

## Reproduce

Apply the repository patch and build its overlay from a dedicated empty build
directory:

```bash
BUILD_ROOT=/path/to/empty-build-root \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-rmsnorm-serial-image.sh
```

Launch the fail-closed qualified profile. The wrapper pins the validated image
identity and the graph, RMS, GDN, MTP, W8A16, and deterministic-compiler
settings; the caller supplies only portable local paths and capacity:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/path/to/new-empty-runtime-cache \
MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 MAX_NUM_BATCHED_TOKENS=1024 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-strict-server.sh
```

Use the repository strict runner twice with separate fresh cache and evidence
directories, then compare complete token arrays with
`scripts/compare-strict-attempt-outputs.py`. One successful attempt is not a
promotion result.

## Evidence

The machine-readable summary is
[`../data/2026-08-28-qwen38-fp8-mtp1-deterministic-r32.json`](../data/2026-08-28-qwen38-fp8-mtp1-deterministic-r32.json).
Complete raw token/timing receipts, canaries, runtime identities, server logs,
and target comparisons are in
[`r32-A`](../data/qwen38-fp8-mtp1-deterministic-r32a/) and
[`r32-B`](../data/qwen38-fp8-mtp1-deterministic-r32b/). The implementation is
the [RMSNorm patch](../patches/vllm-qwen38-xpu-gemma-rmsnorm-mtp1-serial-exact-r30-20260828.patch),
with its [100-trial operator proof](../data/2026-08-28-qwen38-gemma-rmsnorm-mtp1-serial-r30-operator-proof.json).
