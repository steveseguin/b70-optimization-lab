# DeepSeek V4 Flash K160 on 4x B70, 80.820 tok/s

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

This is the standalone, fail-closed launcher for the best verified result from
the paused DeepSeek V4 Flash lane. It reproduces the measured source and flag
identity rather than the later experimental development heads.

## Result

- Model: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`.
- Hardware: four Intel Arc Pro B70 32 GB GPUs, TP4 plus expert parallelism,
  one active generation.
- Target: unchanged experimental uniform-K160 checkpoint; FP8 block-scaled
  dense weights, MXFP4 experts, FP8 KV.
- Draft: DSpark7 revision `aa22cb07426656189b2573b8e77a9b7333b8ae0f`,
  exact M=7 draft queries and M=8 target verification.
- Strict suite medians: `80.820052`, `76.900178`, and `78.287226 tok/s`.
- Reported record high: `80.820052 tok/s`; three-suite median-of-medians:
  `78.287226 tok/s`; p10 on the high suite: `71.669556 tok/s`.
- Validity: 36/36 realistic requests fresh and cache-zero; 24/24 ordered exact
  canaries; target-verified accepted tokens.
- LocalMaxxing: `cmrquta9905w3lg013m5vxoqx`.

This is not aggregate serving throughput. The public K160 checkpoint is an
experimental hash-pruned uniform-K160 artifact with unavailable calibration;
it must not be described as the official checkpoint or as reproducible true
REAP ranking.

## Exact source identity

| Component | Restore prerequisite | Record commit | Archive |
| --- | --- | --- | --- |
| vLLM | public upstream `382bbd51448b2f58c73b3e51d051bc352166ba91` | `264c7f2f7df21ddeeab32ecca0353133344f1ac9` | `patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.bundle` |
| vLLM XPU kernels | `dda91d171fbc3f51d1d65a7f8839714b1efffd42` | `31315673737d95da0f79179c8f755260ef02c1d6` | `patches/deepseek-v4-flash-reap-xpu-b70/vllm-xpu-kernels-deepseek-v4-k160-80tps-record-20260718.bundle` |
| oneCCL | `66499938b7a8b615e26361c52900e7aec306ce50` (2021.17.2) | `48fda4f0e074db005596d6899d5227d3f0316c12` | `patches/deepseek-v4-flash-reap-xpu-b70/oneccl-deepseek-v4-b70-wideepoch-record-20260715.bundle` |

The corrected vLLM bundle includes the previously unpublished experimental base
`61c87db645c256651b5a366f538898485077ad32` and all later record commits.
Its only prerequisite is verified official-upstream commit
`382bbd51448b2f58c73b3e51d051bc352166ba91`. The adjacent vLLM `.patch`
is a reviewable diff from the experimental base, not a standalone restoration
artifact.

First validate the vLLM bundle's checksum, declared prerequisite, public
provenance, disposable restore, record commit, and record tree:

```bash
repo=/home/steve/llm-optimizations
python3 "$repo/tools/validate-git-bundle-provenance.py" \
  --manifest "$repo/patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.provenance.json" \
  --provenance-repo /home/steve/src/vllm
```

Then fetch from source clones containing the declared prerequisites:

```bash
repo=/home/steve/llm-optimizations
git -C /home/steve/src/vllm fetch \
  "$repo/patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.bundle" \
  'refs/tags/deepseek-v4-k160-vllm-record-20260718:refs/heads/deepseek-v4-k160-record'
git -C /home/steve/src/vllm worktree add --detach \
  /home/steve/src/deepseek-v4-vllm-record-264c7f2f7-exact \
  264c7f2f7df21ddeeab32ecca0353133344f1ac9

git -C /home/steve/src/vllm-xpu-kernels fetch \
  "$repo/patches/deepseek-v4-flash-reap-xpu-b70/vllm-xpu-kernels-deepseek-v4-k160-80tps-record-20260718.bundle" \
  'refs/tags/deepseek-v4-k160-xpu-kernels-record-20260718:refs/heads/deepseek-v4-k160-record'
git -C /home/steve/src/vllm-xpu-kernels worktree add --detach \
  /home/steve/src/deepseek-v4-xpu-kernels-record-313156737-exact \
  31315673737d95da0f79179c8f755260ef02c1d6

git -C /home/steve/src/oneCCL fetch \
  "$repo/patches/deepseek-v4-flash-reap-xpu-b70/oneccl-deepseek-v4-b70-wideepoch-record-20260715.bundle" \
  'refs/tags/deepseek-v4-b70-oneccl-record-20260715:refs/heads/deepseek-v4-b70-record'
git -C /home/steve/src/oneCCL worktree add --detach \
  /home/steve/src/oneccl-2021.17.2-b70-sizegate \
  48fda4f0e074db005596d6899d5227d3f0316c12
```

The historical vLLM bundle with SHA-256
`cebc81bedc22496dc82836b9419428e0377a3eb4e7ac213014a7306c7b30e825`
is preserved beside the corrected archive. It remains thin, but its exact
prerequisite and record are now public under narrowly scoped tags. The direct
record tag is the shortest public recovery route. To exercise the historical
bundle itself, fetch only its exact base tag first:

```bash
repo=/home/steve/llm-optimizations
git fetch https://github.com/steveseguin/vllm.git \
  'refs/tags/deepseek-v4-k160-vllm-base-20260714:refs/tags/deepseek-v4-k160-vllm-base-20260714'
git bundle verify \
  "$repo/patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718.bundle"
git fetch \
  "$repo/patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718.bundle" \
  'refs/tags/deepseek-v4-k160-vllm-record-20260718:refs/heads/deepseek-v4-k160-record-historical'
```

See the public
[base tag](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-base-20260714),
[record tag](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-record-20260718),
and [incident #38](https://github.com/steveseguin/b70-optimization-lab/issues/38).
The official-upstream-anchored corrected bundle remains preferred because it
does not depend on the incident-specific base tag.

Build vLLM/XPU kernels and oneCCL with the workflow in
[`ORCHESTRATOR_HANDOFF.md`](../../experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md#6-build-workflow).
The measured oneCCL binary SHA-256 was
`53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`.

## Launch

The local model, DSpark pack, virtual environment, and compiled oneCCL runtime
remain outside Git. Their default paths are recorded by the launcher. After
placing them there, run:

```bash
cd /home/steve/llm-optimizations
repro/deepseek-v4-flash-k160-b70-80tps-20260718/run.sh
```

Override `MODEL_PATH`, `DSPARK_DRAFT_PACK`, `VLLM_TREE`, `KERNEL_TREE`,
`ONECCL_SOURCE_TREE`, `ONECCL_LIB_DIR`, or `RUN_DIR` when the same artifacts
live elsewhere. Source commit checks remain mandatory.

## Validate

After the endpoint is ready on `127.0.0.1:18080`, run exact canaries and three
fresh strict suites in the order `canary -> suite -> canary -> suite -> canary
-> suite -> canary`. Commands are in the
[test workflow](../../experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md#7-test-and-promotion-workflow).
Every request must report `cached_tokens=0`. Compare the generated
`identity.txt` field-by-field with the tracked identity and queue metadata
linked from the [result packet](../../results/deepseek-v4-flash-k160-b70/README.md).

## Evidence

- [Result packet](../../results/deepseek-v4-flash-k160-b70/README.md)
- [Record note](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md)
- [Compact result JSON](../../experiments/deepseek-v4-flash-reap-xpu-b70/data/dspark-sharded-target-argmax-record-20260718.json)
- [Closeout](../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)
- [LocalMaxxing queue](../../experiments/deepseek-v4-flash-reap-xpu-b70/localmaxxing/deepseek-v4-flash-k160-tp4-dspark7-sharded-target-argmax-realistic-80.820tok-20260718.queue.json)
- [Approved response](../../data/localmaxxing-responses/deepseek-v4-flash-k160-tp4-dspark7-sharded-target-argmax-20260718.response.json)

Raw run evidence remains outside Git at
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-target-argmax-candidate-20260718T2100Z`.
