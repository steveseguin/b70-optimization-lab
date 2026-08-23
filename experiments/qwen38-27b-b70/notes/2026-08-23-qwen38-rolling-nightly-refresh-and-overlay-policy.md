# Rolling XPU nightly refresh and optimization-overlay policy

Date: 2026-08-23. This note changes the active development base; it does not
rewrite any historical result.

## Decision

Active development follows the newest available upstream code. The rolling
`vllm/vllm-openai-xpu:nightly` tag must be pulled again at the start of active
runtime work, resolved to an immutable repository digest, and launched only by
that resolved digest. A commit-tagged or digest-pinned prior nightly remains a
reproduction/rollback anchor, not the active nightly.

Accepted lab optimizations are a maintained overlay on that moving base.
Source patches, launcher settings, environment, topology, compilation mode,
cache policy, and benchmark identity are inventoried separately. A refresh
must check whether upstream contains each source change, reapply still-needed
accepted changes, and rerun mechanism/correctness/performance gates. A patch is
never silently dropped because it conflicts. Negative and diagnostic patches
remain preserved but are not automatically promoted.

## Resolved image identity

The tag was inspected and pulled on 2026-08-23. Docker reported:

- source tag: `vllm/vllm-openai-xpu:nightly`;
- repository/index digest:
  `sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`;
- linux/amd64 manifest digest:
  `sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a`;
- OCI config digest:
  `sha256:cb9c19dfac25837b09d6f5529df4d81fe55d7b9052dda0025ccc223b79889187`;
- local Docker image ID on this containerd-backed host:
  `sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`;
- image creation time: `2026-08-23T05:09:33.938169411Z`;
- architecture: `linux/amd64`;
- size: `16.4 GB`;
- vLLM source: `a3561ef8e49d3545c4078df43444beb4c98ae124`, commit time
  `2026-08-22T21:34:38-07:00`;
- vLLM package: `0.26.1rc1.dev1120+ga3561ef8e.xpu`;
- Torch `2.13.0+xpu`, Triton `3.7.2+xpu`, transformers `5.15.0`,
  vLLM XPU kernels `0.1.13.2`, Python `3.12.3`.

This source is 18 commits after the certified `e9d1398d9` image. Review of
those commits found no change explicitly aimed at the Qwen3.8 INC W4A16/XPU
graph path. That is not proof of performance equivalence; matched runtime gates
remain required. The image still defines `VLLM_XPU_ENABLE_XPU_GRAPH` and the
`qwen3_next_mtp` method.

The host had no containers, vLLM server, llama-server, or relevant listener
when the pull began. Root storage can hold only one 16.4 GB image. After the old
image identity and absence of dependent containers were verified, its local
copy was removed and the current rolling image was pulled. The old tag, local
ID, source/version identity, raw roots, and cache manifests remain recorded and
the image is recoverable from the registry. The new image leaves about 3 GB
free, so topology caches must be created on ext4 one at a time, sealed/replayed,
and archived deliberately; raw evidence must not be deleted to make room.

## What the 30.2 / 48.9 / 71.7 result actually used

The certified target-only graph column used the stock official image
`nightly-e9d1398d9edfd90fcc1cf783805240e3effec013` with recorded local image
identity
`sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0`.
It had no local vLLM or XPU-kernel patch, no source/DSO overlay, no code mount,
and no image mutation. Therefore there is no hidden source patch to lose while
refreshing this particular frontier.

The optimization overlay that must transfer is:

- the pinned Qwen3.8 AutoRound INT4 model/revision and direct-plus-ordinary
  manifest verification;
- MTP off, F16 dtype/KV, 32K maximum length, one sequence, 1024 batched-token
  ceiling, prefix caching off, `qwen3` parser, thinking disabled;
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`;
- `CCL_ZE_IPC_EXCHANGE=sockets`, `/dev/dri/by-path:ro`, `/dev/dri`,
  `--ipc=host`, and 16 GiB shared memory;
- only `ZE_AFFINITY_MASK` for device selection;
- GPU-memory utilization `0.90` at TP1/TP2 and `0.60` at TP4;
- a fresh ext4 cache per image/topology, with no shared explicit
  TorchInductor/Triton cache path across ranks;
- the exact suite, token-ID capture, cache-zero canary, diagnostic and strict
  99-interval metrics, objective battery, real baseline, 8K needle, and sealed
  cache replay.

Historical diagnostic values remain TP1 `30.2178 / 30.2569`, TP2
`48.8301 / 48.9505`, and TP4 `71.6741 / 71.5488`. Historical strict
natural-EOS values remain TP1 `30.31067504052998`, TP2
`49.01965141150585`, and TP4 `71.29326283364946 / 71.39843006187554`.
They are not lowered or relabeled if the new base regresses.

## Separate source-patch stack

The Qwen3.6-derived native MTP stack reused by Qwen3.8 is a different runtime
identity. Its vLLM/XPU-kernel/oneCCL source bundles, graph-safe attention stage,
ReplaySSM/native-GDN controls, and patches remain preserved under `patches/`,
`repro/`, and the Qwen experiment tree. They must be evaluated change by
change after the stock rolling comparison.

Two recent patches are explicitly not mandatory forward ports:

- `patches/qwen38-27b-mtp-fc-int4-b70/` is quality-clean but rate-neutral and
  default-off;
- the D1/D2 state-audit patch is diagnostic-only and both tested mechanisms
  were eliminated.

Rejected greedy margins, quality-red KV modes, shared-NTFS cache layouts, and
negative/unsafe patches remain evidence, not current defaults.

## Promotion and matrix plan

Use
[`run-20260823-qwen38-rolling-nightly-strict-smoke.sh`](../scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh).
It pulls the rolling tag, resolves one matching immutable RepoDigest, verifies
the tag and digest map to the same image ID, records both identities, launches
only the immutable reference, verifies model bytes through direct and ordinary
reads, and preserves the strict cache/canary/quality contracts. The two dated
old-image launchers remain unchanged.

Qualification proceeds TP1 -> TP2 -> TP4. Each topology needs a fresh cache
and exact replay. Stop before the next topology for an identity, boot, graph,
canary, cache-zero, quality, baseline, needle, token-count, performance, or
cache-immutability failure. Hard performance floors are the lower certified
captures: diagnostic `30.2178 / 48.8301 / 71.5488` and strict
`30.31067504052998 / 49.01965141150585 / 71.29326283364946` at TP1/2/4.
A failure does not replace the old result; if attribution is unclear, swap the
old digest back in for a matched same-host control.

The old 96-cell matrix remains complete for its exact image. The rolling base
first requalifies the promoted MTP0/F16/graph column. After that, use minimal
sentinels to test whether upstream changed a prior gate: TP1 graph+MTP,
TP1 MTP eager cost, and KV backend support/quality. Expand only a sentinel that
changes classification. TP3 remains structurally invalid while the model has
16 GDN K heads, and is represented as such rather than burned again.

For neural.download, the old and new runtime identities remain separate
measured/versioned profiles. The current rolling profile replaces the active
recipe only after qualification; it never erases the certified historical
curve or an optimization-grade record.

## Qualification update

The full MTP0/F16/graph column was characterized on the resolved `a3561ef8`
runtime. Correctness, quality, graph, model-identity, and cache-replay gates
passed at TP1, TP2, and TP4. Performance did not justify wholesale replacement:
TP1 strict repeated about 0.22% below the pinned result, TP2 strict was 1.08%
below it, and a TP4 strict 71.9002 high fell to 71.2457 on exact same-cache
repeat. The old frontiers remain unchanged.

The compiled graphs and candidate autotune sets are identical across old and
new images, but the package-version cache key forced fresh tuning and changed
many `.best_config` winners. The capped TP2 transfer recovered the newest
strict rate from 48.4905 to 49.0094 tok/s with full quality and immutable cache,
but missed the frozen 49.0197 promotion gate by 0.021%. It is preserved as a
quality-certified near-recovery, not promoted. TP4 is a separate preregistered
mapping with a mandatory same-cache stability repeat. See the
[qualification note](2026-08-23-qwen38-rolling-nightly-a3561ef8-qualification.md)
and [TP2 overlay closure](2026-08-23-qwen38-tp2-autotune-winner-overlay-result.md).
