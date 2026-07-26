# Laguna S 2.1 on 4x B70: published 102.971 / conventional 101.942 tok/s

This is the fail-closed lab reproduction for the approved Laguna S 2.1 INT4
four-B70 result. It restores the measured source and runtime identity, runs
one cold 13-prompt suite, and rejects token, text, cache, treatment, graph, or
teardown drift.

## Result and metric qualification

| field | value |
| --- | ---: |
| LocalMaxxing/submitted historical convention | `102.97143559613157 tok/s` |
| Conventional first-to-100th-token interval rate | `101.94172124017027 tok/s` |
| Canonical-q1 equality | `13/13` token IDs and output-text SHA-256 |
| Cache state | `cached_tokens=0` on `13/13` rows |
| LocalMaxxing | [`cms2ccv2d00lps201rej94pjy`](https://www.localmaxxing.com/en/runs/cms2ccv2d00lps201rej94pjy) (`APPROVED`) |

The historical helper divided 100 timestamped events by a span containing 99
inter-token intervals. The public value is an accurate receipt of that
submitted convention, but it is not a conventional 102 tok/s result. See the
[accounting correction](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md).

No duplicate LocalMaxxing submission is needed or allowed for this packet.

## Exact identity

- target: `poolside/Laguna-S-2.1-INT4` revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft: `poolside/Laguna-S-2.1-DFlash-INT4` revision
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- hardware: four Intel Arc Pro B70 32 GB cards, TP4+EP4, one active
  generation;
- vLLM: `e596ef1543466ae1a05e5bb8091f58872e2b18ba`;
- XPU kernels: `6f9dd3c3a7b1b677a992ca4f431a968408f9c816`;
- target verifier width 12, DFlash depth 11, BF16 KV;
- exact Breakable PIECEWISE topology: 146 graph segments and 145 eager breaks
  per rank;
- treatment: exactly 31 runtime E4M3FN W8A16 DFlash projection conversions per
  rank.

The FP8 label refers to draft projection weights, not KV. The record
deliberately uses BF16 KV to preserve its canonical-teacher contract.

## Verify the historical packet

This performs no GPU work and no network submission:

```bash
cd /home/steve/llm-optimizations
repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-record.sh
```

When the sealed raw run is mounted, it verifies all tracked raw hashes,
recomputes both throughput conventions from token timestamps, and compares all
13 token streams and output-text hashes against the compact tracked oracles.
Without the raw mount it still validates the packet, source snapshots,
LocalMaxxing queue, and approved receipt.

## Restore source

Starting from upstream clones that contain the public bases:

```bash
repo=/home/steve/llm-optimizations

git -C /home/steve/src/vllm fetch \
  "$repo/patches/laguna-s-2.1-xpu-b70/vllm-laguna-width12-dflash-fp8-102tps-record-20260726.bundle" \
  experiment/laguna-width12-stack-clean-20260726:refs/heads/laguna-record
git -C /home/steve/src/vllm worktree add --detach \
  /home/steve/src/laguna-vllm-width12-stack-clean-20260726 \
  e596ef1543466ae1a05e5bb8091f58872e2b18ba

git -C /home/steve/src/vllm-xpu-kernels fetch \
  "$repo/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-width12-102tps-record-20260726.bundle" \
  experiment/laguna-width12-router-clean-20260726:refs/heads/laguna-record
git -C /home/steve/src/vllm-xpu-kernels worktree add --detach \
  /home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726 \
  6f9dd3c3a7b1b677a992ca4f431a968408f9c816
```

The source bundles and reviewable combined patches are indexed in the
[snapshot README](../../patches/laguna-s-2.1-xpu-b70/README.md).

## Runtime and model prerequisites

The exact lab replay expects:

- virtual environment `/home/steve/.venvs/deepseek-v4-xpu`;
- target and draft below
  `/mnt/fast-ai/llm-models/laguna-s-2.1/`;
- the model root on `/dev/nvme0n1p2` as ext4;
- cluster address `10.0.0.65` on an up interface;
- no vLLM worker and no listener on port 18080.

The launcher pins and hashes the Python/vLLM entry points, oneCCL, SYCL,
`libtorch_xpu`, six native XPU modules, model configs, model manifests, source
trees, historical benchmark, interval-accounting qualifier, comparator, suite,
and both compact teacher oracles. It also checks exact package versions.
Override `REPRO_VLLM_TREE`,
`REPRO_KERNEL_TREE`, `REPRO_VENV_ROOT`, or `REPRO_CLUSTER_IP` only when the
same byte-identical artifacts live elsewhere.

This is an exact lab replay, not yet a clean-room build recipe: the original
compiler/build command and a portable model-download manifest were not fully
sealed. A fresh rebuild that does not reproduce the pinned native binary
hashes must be labeled a new environment and revalidated; do not weaken the
checks to make it pass.

## Preflight and run

Preflight performs no model launch:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh --preflight
```

Run exactly one cold suite:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/run.sh --run
```

The policy is one start, one suite, and the first valid score. Do not retry to
select a faster start, warm the model with a generation, omit prompts, enable
prefix/history reuse, or move graph/setup work outside the measured contract.

Validate the resulting directory:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-run.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-width12-dflash-fp8-repro-YYYYMMDDTHHMMSSZ
```

The validator reports both rate conventions. Throughput can vary; identity,
13/13 token-and-text equality, cache-zero state, four treatment markers, and
the 146/145 topology may not.

## Evidence

- [Qualified result packet](../../results/laguna-s-2.1-int4-b70/README.md)
- [Structured record](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json)
- [Original record note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [Campaign transfer ledger](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md)
- [LocalMaxxing ledger](../../results/localmaxxing-submissions.md)
