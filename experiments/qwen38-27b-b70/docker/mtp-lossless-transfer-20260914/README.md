# Native MTP control on the September 14 upstream base

This is an **unqualified control rebase**, prepared separately from the frozen
AMD transfer startup incident. It starts from the XPU nightly freshly pulled by
this campaign, retains the exact accepted FP8/native-MTP overlay, and explicitly
sets `VLLM_USE_V2_MODEL_RUNNER=0`. There is no DFlash configuration or draft model
in this recipe. The parent campaign owns exclusive-device checks, loading, and
all runtime qualification; this recipe performs only a CPU build.

## Preserved numerical contract

The target remains the official FP8 checkpoint, using the accepted native FP8
block-scaled matrix path, FP16 activations and KV, full target vocabulary head,
exact XCCL communication and accepted GDN state handling. Existing draft-only
INT4 head support is preserved as source capability, with its original
native-MTP launch settings owned by the parent; no target arithmetic or head
approximation is introduced here. This control contains no new metadata or
communication candidate.

The 15 audited Python files and the overlay are byte-identical to the previously
reviewed [accepted overlay](../amd-transfer-20260914/README.md). This reuses its
source review, not its failed V2/DFlash launch. The previous incident remains
quarantined. Installed source identities are recorded in
[candidate-python.sha256](candidate-python.sha256), with provenance in
[source-audit.json](source-audit.json).

The fresh nightly resolves to index
`sha256:fa0e2f3966f23d64e1532e45ce2eca2fef619fb63f93d5b9b13cb5bcc0743aec`,
amd64 image `sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41`,
and upstream source `dc36fcce902a63eab06c1b93a5c4a5ee178a0c56`.
Torch remains 2.13.0+xpu, vLLM is 0.29.1rc1.dev47+gdc36fcce9, and
vllm-xpu-kernels is 0.1.14.1. The accepted compiled artifacts are reusable because
the freshly resolved base has the same immutable identity as the previous exact
Torch/native-dependency ABI comparison. The build checks each reused kernel's
SHA-256 against that receipt. No native compilation is needed.

## CPU-only build

```bash
KERNEL_ARTIFACTS_DIR=/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/reused-kernels \
CANDIDATE_CONTEXT=/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/control-build-context \
bash experiments/qwen38-27b-b70/docker/mtp-lossless-transfer-20260914/build-control.sh
```

The context must be new. The build has no network or device mounts and imports
installed vLLM only from `/`; it asserts that neither Torch GPU backend has been
initialized. Image labels and the explicit V1 environment create a separate
control identity. Historical patch application can use Docker's immutable layer
cache; the resulting installed files are independently extracted and hashed.

This local build recipe is not a published reproducible package and claims no
correctness or speed result. Full source identity, runtime mechanism checks,
complete deterministic output gates and matched performance measurements remain
required before adoption.
