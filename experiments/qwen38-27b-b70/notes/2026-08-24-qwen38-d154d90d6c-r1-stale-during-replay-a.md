# d154 r1: fast clean arms stopped stale when vLLM main advanced

Date: 2026-08-24. Status: **closed failed-incomplete/stale after the fresh
diagnostic and strict replay A, with a separately identified cache-directory
delta; replay B did not start and d154 is not qualified.**

## Outcome

The fresh hardware gate passed completely on boot
`086de284-0771-4269-9cb2-e064fe303e40`: four-device identity, per-card
compute, peer read, four-rank XCCL barrier/all-reduce, coherent runtime,
SMART/ext4/root-NVMe checks, zero kernel taint, and clean postflight. Its
sealed root is:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-d154d90d6c-20260824-086de284-venvlib-r1
```

The untreated zero-overlay candidate then ran from image
`sha256:358fb358a30463ededcb9ead252d0841b29eeeac684be756e16528329cb1030e`
under the exact frozen model, graph, cache, timing, and environment contract.
No TP decision overlay, source patch, DSO, generated binary, or imported
prior-campaign cache was applied; replay A deliberately consumed the cache
created by this campaign's fresh arm. The campaign root is:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-d154d90d6c-20260824-r1
```

Two arms produced unusually strong but incomplete evidence:

- the fresh diagnostic passed its exact canary, 25-row realistic benchmark,
  cache sealing, source checks, kernel guards, and cleanup. Its conventional
  99-interval median was `30.35213813941521 tok/s`, above the frozen
  `30.2178` floor by `0.13433813941521` and above the protected diagnostic
  high `30.2569` by `0.09523813941521`;
- strict replay A passed its exact canary, 25-row natural-EOS benchmark,
  byte-immutable regular-file cache check, and full quality battery. Its observed median was
  `30.3562353617713 tok/s`, above the frozen strict floor
  `30.31067504052998` by `0.04556032124132` and above the qualified 0ecc
  strict high `30.325970521145816` by `0.030264840625484`. Quality was an
  exact baseline match: 7/7 exact cases, 8/8 repeat-stability runs with one
  hash, the 8K needle at 7,617 actual prompt tokens, and all 24 baseline
  comparisons.

Neither observation is promotable. After replay A's workload and clean
shutdown, its mandatory freshness check found that vLLM `main` had advanced
from `d154d90d6c4bcf26a0c78ac4f3e43621c14333ba` to
`a0f1b9ad05452ae5e73764dcf4cc11463be7807c`. XPU-kernel main remained
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and the official nightly
remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The strict runner therefore wrote `stale-before-promotion` and exited 5 before
the outer wrapper could write the strict speed-gate file. Replay B correctly
remained absent, so d154 is incomplete: it does not replace a protected high,
qualify a website cell, authorize a TP1 decision packet, or open TP2/TP4.

An adversarial post-close audit found a second, independent reason not to
promote. All 1,097 regular cache files and their bytes were identical across
fresh-post, replay-A-pre, and replay-A-post, but the full directory set changed
from 213 to 214 entries. Replay A added exactly one empty real directory,
`vllm/dummy_cache`; nothing was removed. This is deterministic upstream
behavior: `vllm/compilation/caching.py` creates that directory while loading
standalone AOT artifacts with `disable_cache=true`. The stale exit occurred
before the outer wrapper's next full-tree validation, which otherwise would
have rejected the directory delta before replay B. Therefore this packet does
not claim that every non-speed/cache gate passed.

The outer campaign failure JSON called the exit `unclassified wrapper or
command failure`. That label is a narrow provenance defect, not the cause of
the stop. The exact runner has one exit-5 path, and the sealed replay status,
pre/post refs, benchmark, quality, cache, kernel, and cleanup evidence prove
this was the expected stale-before-promotion path. The successor wrapper will
recognize exit 5 only when the exact arm status is `stale-before-promotion`;
other nonzero combinations remain fail-closed. The frozen d154 wrapper and
shared runner are not rewritten.

## Evidence integrity

The hardware manifest verifies 70/70 entries and hashes to
`46fd68ef3d31a2366190f695ffe18722115356d26f46177d4793b4c7dd9bd70e`.
The campaign manifest verifies 436/436 entries and hashes to
`4d775bc651780bf681bcc5ae0e6321e87a149c6b11ddb45132658abec889cba8`.
The frozen input manifest verifies 270/270 entries and hashes to
`3dfa5514f2844e63d9a6a3a2306e34085afbb1ebd0b1a0287fd838555be6976a`.
The compiled-cache regular-file manifest verifies all 1,097 files at
`cb2dcf665bfbb8d983e74c89138e47a87ea37ea541f849f350bf8ad589e2a7b1`;
replay A's pre/post regular-file manifests are byte-identical. The frozen
213-directory manifest is
`15886d56edf753d2fdb10e0a6393ef8dc0375478cf735b4c9f47e37933b4f677`;
the 214-directory post-replay tree hashes to
`cba4f9cc0fa8bc456f79854e86050f442a2ea8c4b13e11811a5ea117d7aa8ad1`.

Both executed workloads and their cleanups retained zero kernel taint, zero
matching kernel reject events, no render holder, and no residual container.
Close-time movement of
the lab repository from frozen `b9fd0c6b6` to live `9d21d1ab3` was recorded
but was deliberately non-gating: the local lab snapshot and all frozen inputs
remained immutable during the run. The full machine-readable record is
[`2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.json`](../data/2026-08-24-qwen38-d154d90d6c-r1-stale-during-replay-a.json).

## Forward port and next action

`a0f1b9ad` is the direct child of d154. Its complete delta is one CI test
line: FLEX_ATTENTION absolute tolerance changes from `0.006` to `0.00875` in
`tests/entrypoints/pooling/scoring/test_cross_encoder_online_vision.py`.
There is no serving, Qwen3.5/MTP, XPU, build, C++, Rust, or batch-invariance
source change. Runtime equivalence does not permit relabeling d154 artifacts
as a0f1: SCM identity and cache namespaces change, so a new wheel, receipt,
and image are required.

The successor wrapper must normalize the newly understood cache structure
without weakening it: after the fresh arm, first assert that
`vllm/dummy_cache` is absent, then create and verify that exact root-owned,
mode-0755, empty real directory before freezing the directory manifest.
Freeze the successor's own regular-file and directory manifests; both must
remain exact through replay A and B, and `dummy_cache` must remain empty. This
changes no server argument, graph, decision, or timed workload; it prevents
ordinary upstream AOT replay initialization from looking like unbounded cache
mutation.

Build a0f1—or any newer literal vLLM `main` that exists at the build gate—with
the live XPU-kernel main and official nightly. Preserve the batch-invariance
assets, reusable Rust inputs, protected speed ledger, and the exact 78-file
TP2 and 152-file TP4 bundles. Qualify untreated TP1 first; only then derive
any required TP1 decision packet, followed by TP2 zero-overlay plus a fresh
78-decision remap and TP4 zero-overlay plus a fresh 152-decision remap. MTP and
broader website matrix work remain downstream of those target-only anchors.
