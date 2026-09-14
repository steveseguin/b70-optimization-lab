# September 14 AMD transfer: refreshed accepted overlay

**Do not launch this candidate unchanged.** The first V2/DFlash2 attempt coincided with a user-reported host freeze during target loading, before readiness. The user restarted the host; no DFlash2 output or speed result exists. Preserve this source packet for diagnosis. See the [incident](../../data/2026-09-14-amd-transfer/freeze-incident.json).

This is an **unqualified candidate build recipe**, not a promoted runtime. It
ports the complete R304 Python overlay onto the newest XPU nightly resolved at
campaign start. It does not add DFlash, change target precision, or enable an
approximate target head. The parent campaign owns runtime testing and service
coordination.

## Identities and source reconstruction

- Source tag: `vllm/vllm-openai-xpu:nightly`.
- Registry index: `sha256:fa0e2f3966f23d64e1532e45ce2eca2fef619fb63f93d5b9b13cb5bcc0743aec`.
- Linux amd64 image: `sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41`.
- [Upstream source](https://github.com/vllm-project/vllm/tree/dc36fcce902a63eab06c1b93a5c4a5ee178a0c56): `dc36fcce902a63eab06c1b93a5c4a5ee178a0c56`.
- Its [XPU dependency pins](https://github.com/vllm-project/vllm/blob/dc36fcce902a63eab06c1b93a5c4a5ee178a0c56/requirements/xpu.txt)
  remain Torch 2.13.0, Triton 3.7.2+xpu and vllm-xpu-kernels 0.1.14.1.
- Kernel source stays `6d92b1bfbf32767ecda8e819613eb151e70030ad` and already
  includes upstream GDN fix #544. oneDNN stays
  `0e2a5bfeef1bfbffc3137464606540233086ce9b` plus accepted r137a/r137b/r221;
  sycl-tla stays `cd763790ad2f74d7294435ecf77682bac0062c3a`.

All 15 Python files in the R304 17-file contract were reconstructed using public
v0.29.0 source, the checked-in `rebase-v0290/ported-files`, and R302/R303/R304
patches. Every reconstructed file matches its frozen contract SHA-256. The two
remaining contract files are compiled kernel libraries. No accepted overlay was
inferred from marker searches alone.

A three-way source merge used newest upstream, stock v0.29.0, and that exact R304
reconstruction. The result changes 12 newest-upstream files. The input and output
hash manifests cover all 15 audited Python files; [source-audit.json](source-audit.json)
records their identities. The build refuses a different installed source tree.

## Explicit conflict decisions

There were six conflict regions in five files:

| File | Decision |
| --- | --- |
| `_xpu_ops.py` | Follow upstream's removal of the no-op fake function; preserve explicit convolution and SSM state arguments and mutation declarations. The real GDN function remains AST-identical to R304. |
| `layernorm.py` | Preserve the lab's GemmaRMSNorm native XPU path instead of selecting upstream's new fused path. This class also serves Qwen normalization, so preserving it matters for target exactness. The new fused route is deferred pending a separate numerical gate. |
| `vocab_parallel_embedding.py` | Retain the draft-only INT4 head and shortlist, followed by upstream's expanded XPU batch-invariant branch. No approximate target head is introduced. |
| `mixed_precision/xpu.py` | Preserve deterministic W4 padding, adapting the weight accessor to upstream's three-value API and passing `None` to the retained external kernel ABI argument. |
| `flash_attn.py` | Retain the existing default-off serial verification switch before upstream's new FA4 callable. It is not enabled in the FP8 recipe. |

The GDN layer, metadata builder, V1 proposer and uniform-decode guard merge
without conflicts. Upstream has not absorbed the three R302/R303/R304 fixes:
uniform-decode alias protection, first-chunk classification, and active runtime
width. They remain applied. Keep R306 dynamic scheduling and unpromoted
R307/R308 experiments in their separate historical lanes; this refresh does not
silently promote them. Existing environment, launcher, cache, compilation and
topology settings still need explicit preservation at launch.

An independent source review found the active GDN implementation, state binding,
FP8 block-scaled GEMM class, native normalization, FP16 GEMM dispatch and draft
copy function AST-identical to served R304. XPU communicator source is identical.
This supports the port's intent; it cannot replace compilation and output gates.

## Build: reuse only after exact native identity

The nightly still pins the same kernel source and Torch release. Reusing the
accepted native artifacts avoids an unnecessary rebuild **only when** exact
binary identities also match. The screen hashes `torch/version.py`, `_C*.so`, all
`torch/lib/*.so*`, and resolved SYCL/C++/GPU-loader dependencies in both local
images. It imports no Torch or model code and exposes no GPU. On any mismatch it
stops; rebuild instead. It also checks copied kernels against historical hashes.

After the parent resolves and pulls the immutable image:

```bash
python3 experiments/qwen38-27b-b70/docker/amd-transfer-20260914/reuse-kernels-if-identical.py \
  --output /mnt/fast-ai/build/amd-transfer-20260914-reused-kernels

KERNEL_ARTIFACTS_DIR=/mnt/fast-ai/build/amd-transfer-20260914-reused-kernels \
CANDIDATE_CONTEXT=/mnt/fast-ai/build/amd-transfer-20260914-context \
bash experiments/qwen38-27b-b70/docker/amd-transfer-20260914/build-candidate.sh
```

Both output directories must be new. The first command performs two bounded
CPU-only hash processes and creates one stopped container solely to copy the
accepted artifacts. The candidate Docker build checks installed upstream hashes,
applies the overlay without fuzz, checks output hashes and parses all files. Its
CPU import check runs from `/` and verifies it loaded installed vLLM from
`/opt/venv`, avoiding the image's source-checkout working directory.

## Fallback: rebuild the same accepted native sources in the new image

```bash
BUILD_ROOT=/mnt/fast-ai/build/amd-transfer-20260914-kernels \
JOBS=10 \
bash experiments/qwen38-27b-b70/docker/amd-transfer-20260914/build-kernels.sh

BUILD_ROOT=/mnt/fast-ai/build/amd-transfer-20260914-kernels \
CANDIDATE_CONTEXT=/mnt/fast-ai/build/amd-transfer-20260914-context-rebuilt \
bash experiments/qwen38-27b-b70/docker/amd-transfer-20260914/build-candidate.sh
```

Historical same-source builds took about 13 minutes; the recorded clean-clone
rebuild took **1,046 seconds** at 10 jobs. Its two artifacts total 64,648,968 bytes.
That is evidence for planning, not a guaranteed duration or measured peak RAM.
The wrapper defaults to a 14 GiB memory cap and a 14 GiB combined memory/swap cap,
with no device mounts. Host oneAPI 2026.1 is mounted read-only. The parent must
schedule it around actual available host memory; `JOBS`, `BUILD_MEMORY` and
`BUILD_MEMORY_SWAP` can be lowered explicitly. No host swap or power settings are
changed. No automatic retry or service cycling is included.

## Validation status before runtime qualification

- All 15 reconstructed R304 Python hashes match the historical contract.
- The new patch applies to pinned upstream with zero fuzz; all 15 candidate
  hashes and Python AST parses match afterward.
- Both shell scripts pass `bash -n`; the reuse helper parses successfully.
- Independent source review found no concrete defect in the active FP8 port.
- No build, GPU execution, output-quality test or speed measurement was performed
  by this source-preparation subtask. The campaign's later results own those.

Use V1 for the initial accepted-overlay comparator. Re-run the full image
identity diff, compilation/mechanism checks, strict output and determinism gates,
short-prompt boundary checks, representative longer-context checks, and matched
prefill/decode timing before promotion. A DFlash/V2 experiment requires its own
overlay integration and qualification; this base port does not claim to supply it.
