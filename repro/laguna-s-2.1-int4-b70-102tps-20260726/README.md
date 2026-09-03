# Laguna S 2.1 on 4x B70: published 102.971 / conventional 101.942 tok/s

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

This is the fail-closed reproduction packet for the approved Laguna S 2.1
INT4 four-B70 result. It embeds the sealed raw evidence, restores every known
source and model revision, verifies actual native loader origins, runs one cold
13-prompt suite, and rejects token, text, cache, treatment, graph, teardown, or
material performance drift.

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
cd /path/to/b70-optimization-lab
repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-record.sh
```

The sealed raw benchmark, exactness report, server log, identity, service
environment, metrics, cleanup status, and all pre/post idle snapshots are
tracked below `evidence/record-run/`. Verification therefore fails if evidence
is absent; it never degrades to a packet-only PASS. The command recomputes both
throughput conventions and compares all 13 token streams and output-text
hashes against the compact tracked oracles.

## Restore source

The portable restore command fetches public prerequisites, imports all three
tracked bundles, and creates five clean worktrees covering the mixed native
provenance:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-sources.sh \
  /mnt/fast-ai/laguna-repro-sources
```

The source bundles and reviewable combined patches are indexed in the
[snapshot README](../../patches/laguna-s-2.1-xpu-b70/README.md). Build and
provenance details are in [BUILD.md](BUILD.md).

Restore or verify the two model payloads at their immutable Hugging Face
revisions:

```bash
repro/laguna-s-2.1-int4-b70-102tps-20260726/restore-models.sh \
  --download /mnt/fast-ai/llm-models/laguna-s-2.1
```

The tracked manifest contains exactly 32 release files and excludes `.cache`
locks, metadata, and incomplete downloads.

The originating host additionally keeps a 118-entry snapshot of the whole
model directory, release files plus Hugging Face download-cache metadata, at
`<model root>/.verification/source-files.sha256` and
`<model root>/.verification/nvme-files.sha256`; the launchers hash-pin that
snapshot and re-check the directory against it. It is tracked here as
[`manifests/model-directory-verification.sha256`](manifests/model-directory-verification.sha256).
On another host, copy it to both `.verification/` names after the download.
Its `.cache/huggingface/` entries record the originating download and are not
expected to match a fresh download byte-for-byte; that part of the check is
originating-host identity rather than payload verification.

## Runtime and model prerequisites

The exact lab replay expects:

- virtual environment `/home/steve/.venvs/deepseek-v4-xpu`;
- target and draft below
  `/mnt/fast-ai/llm-models/laguna-s-2.1/`;
- the model root on `/dev/nvme0n1p2` as ext4;
- cluster address `10.0.0.65` on an up interface;
- no vLLM worker and no listener on port 18080.

The launcher pins and hashes the Python/vLLM entry points, oneCCL, SYCL,
`libtorch_xpu`, four extension modules, six transitively loaded helper DSOs,
`xpumem_allocator`, model configs, the release payload and original manifests,
source trees, historical benchmark, interval-accounting qualifier, comparator,
suite, and both compact teacher oracles. It also checks exact package versions,
four B70 PCI identities, OS/kernel identity, cluster interface, model
contents, and actual module and `/proc/self/maps` loader origins.
Override `REPRO_VLLM_TREE`,
`REPRO_KERNEL_TREE`, `REPRO_VENV_ROOT`, `REPRO_XPUMEM_MODULE`,
`REPRO_CLUSTER_IP`, `REPRO_MODEL_ROOT`, `REPRO_ARTIFACT_ROOT`,
`REPRO_NVME_DEVICE`, or `REPRO_NVME_FSTYPE` only when the same byte-identical
artifacts live elsewhere; an absent default stops the launcher with a message
naming the variable.

The original single monolithic build invocation was not sealed. The packet
therefore distinguishes a portable sealed-evidence audit, an artifact-exact
originating-host replay, and a source-equivalent rebuild. A fresh rebuild that
does not reproduce the pinned native binary hashes is a new environment and
must pass the complete gate; do not weaken or replace the sealed hashes to
make it look artifact-exact.

## Preflight and run

Complete preflight performs no model launch. It hashes the full model payload,
so it is intentionally slower than a shallow syntax check:

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

The validator reports both rate conventions. Identity, 13/13 token-and-text
equality, cache-zero state, four treatment markers, 146/145 topology, service
environment, and cleanup/idle evidence may not drift. To distinguish “correct
but much slower” from reproducing the performance result, it also requires a
conventional suite median of at least `96.844635178 tok/s` (95% of the sealed
conventional median).

The post-packaging hardening has been validated with component checks of the
sealed evidence, runtime loader mapping, source bundles, and model manifest.
The integrated `run.sh --preflight` and a fresh source restore were not rerun
after packaging: the former is intentionally left for a clean committed
checkout, and the latter encountered a pathological local partial-clone fetch
loop. No additional score-bearing cold suite was consumed; the tracked scored
evidence remains the sealed first-valid historical run.

## Evidence

- [Qualified result packet](../../results/laguna-s-2.1-int4-b70/README.md)
- [Structured record](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json)
- [Original record note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [Campaign transfer ledger](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md)
- [Reproducibility provenance audit](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-reproducibility-provenance-audit.md)
- [LocalMaxxing ledger](../../results/localmaxxing-submissions.md)
