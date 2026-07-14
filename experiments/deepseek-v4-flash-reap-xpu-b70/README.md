# DeepSeek V4 Flash REAP/XPU On Four B70s

This is the active experiment packet for constructing and optimizing an
Intel-native, full-resident DeepSeek V4 Flash derivative for one active
generation on four Arc Pro B70 32 GB GPUs.

Read in order:

1. [controlling investment-gated plan](../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md);
2. [current handoff](HANDOFF.md);
3. [stage gates](benchmarks/stage-gates.md);
4. [quality contract](quality/README.md);
5. [experiment ledger](results/experiment-ledger.md).

## Frozen Identity

- official source: `deepseek-ai/DeepSeek-V4-Flash`
- source revision: `60d8d70770c6776ff598c94bb586a859a38244f1`
- first runnable smoke candidate: uniform-K160
  `0xSero/DeepSeek-V4-Flash-180B` revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`
- quality-controlled candidate: later official-source, hash-preserved K160
- later capacity candidates: K168, K176, K180
- hash layers 0-2: preserve all 256 experts
- later layers 3-42: use the frozen candidate-specific expert map
- production runtime: vLLM/XPU plus `vllm-xpu-kernels`
- precision bakeoff: native MXFP4/BF16 versus symmetric group-128 INT4/BF16
- initial context: 8K
- workload: one active generation, never aggregate throughput
- speculation: disabled until correct nonspeculative decode approaches
  40-50 tok/s

The old
[`../deepseek-v4-flash-autoround-vllm/`](../deepseek-v4-flash-autoround-vllm/README.md)
packet remains rejected fit/support evidence for the oversized Intel AutoRound
artifact. Do not mix its configs, model identity, results, or LocalMaxxing
templates into this lane.

## Current Status

The user explicitly authorized the frozen public K160 download while the small
gates continue. The snapshot is 46 standard safetensors shards totaling
`103107582016` bytes and includes MTP entirely in shard 46. Preserve the full
archive, even though initial nonspeculative loading skips `mtp.*` tensors.

This K160 is for fast Intel bring-up, not automatic promotion. It uses one
global 160-expert layout, including layers 0-2, and its unavailable calibration
snapshot means its rank-discounted top-k frequency cannot be represented as
true REAP. The original hash-preserving nested-pack plan remains the quality
path after the official-source teacher is available.

The immediate work is deliberately small:

- use the clean pinned DeepSeek-specific runtime worktrees;
- prove exact-shape native MXFP4 and INT4 MoE kernels on B70;
- add and test heterogeneous per-layer expert counts with dummy weights;
- pass DeepSeek V4 sparse-attention/cache/mHC fixtures;
- freeze ranking provenance, quality-suite identity, numerical tolerances, and
  storage budgets before the large download.

## Promotion Rules

Every candidate must be labeled as a REAP-pruned derivative with exact K,
manifest hash, packing format, source revision, and runtime identity. It must
never be reported as the unmodified 284B checkpoint.

Promotion requires:

- fully resident execution with no CPU/SSD expert offload;
- native low-bit kernel traces and no BF16 expert expansion;
- at least 3 GiB free on every GPU after warm 8K graph capture;
- the fixed quality contract;
- the fixed realistic cold suite with `cached_tokens=0`;
- complete profile, repeatability, and artifact capture.

Do not create a `repro/` packet or LocalMaxxing submission until a complete
full-model candidate passes those gates.

## Folder Map

- `benchmarks/`: stage gates and later benchmark identities;
- `data/`: fit audits, manifests, compact summaries, and hashes;
- `quality/`: teacher/control suite and promotion contract;
- `results/`: append-only experiment ledger;
- `patches/`: source/config deltas, including failed attempts;
- `scripts/`: helpers added only as their stage begins.
