# Real Engine resident allocation forecast

This source-only ledger counts actual requested allocation bytes for the generic GSQ integration at context 4096. It does not qualify physical fit or authorize a model load. No Device, model payload, or executable was invoked.

| Split / mode | Rank 0 bytes (GiB) | Rank 1 bytes (GiB) | Rank 0 / rank 1 headroom below 30 GiB |
|---|---:|---:|---:|
| split22-26_target-only | 24,216,508,948 (22.5534) | 31,965,427,828 (29.7701) | 7,995,745,772 / 246,826,892 |
| split22-26_mtp-rank0 | 28,410,194,762 (26.4591) | 31,965,427,828 (29.7701) | 3,802,059,958 / 246,826,892 |
| split23-25_target-only | 25,416,953,512 (23.6714) | 30,768,586,090 (28.6555) | 6,795,301,208 / 1,443,668,630 |
| split23-25_mtp-rank0 | 29,610,639,326 (27.5771) | 30,768,586,090 (28.6555) | 2,601,615,394 / 1,443,668,630 |
| split24-24_target-only | 26,523,118,164 (24.7016) | 29,672,451,988 (27.6346) | 5,689,136,556 / 2,539,802,732 |
| split24-24_mtp-rank0 | 30,716,803,978 (28.6073) | 29,672,451,988 (27.6346) | 1,495,450,742 / 2,539,802,732 |

The existing default with `draft_rank=0,target_split=0` is **22/26**, not 24/24. The requested 24/24 layout requires explicit `--target-split 24`. Both target-only and MTP rows use the same target tensors, full vocabulary and BF16 state. These numbers do not select or launch a configuration.

## What is counted

The ledger follows the real generic Builder, removes the four single-card handoff/control sites, then applies the actual rank split. Its 1,869 logical launch count matches the retained real-header preflight. The old graph has 1,873 entries before this transformation. Index-selection budget 2,048 is independent of context 4,096: each QSA layer has keys/values `[4096,2,256]`, raw `[4096,128]`, and pooled `[1024,128]`, totaling 9,699,328 bytes. A 24/24 split has six QSA layers per rank.

All 1,222 non-lookup target tensors are accounted exactly once across ranks. Only weights referenced by actual retained launches load; a mask-3 placement permission does not allocate unused replicas. The target Q6 head expands from 521,472,000 to 839,321,600 bytes; F16 primitive controls add 81,920 bytes after widening. Host embedding and PLE backing total 29,137,853,440 bytes and are not charged as resident device weights.

Each rank includes every retained plan buffer, 256 MiB operator scratch, 8 MiB GEMV workspace, attention scores/probabilities, prepared FP32 input, all-layer snapshots, route/mixture controls, 4 MiB rope table and the unconditional 65,536-byte probe discard buffer. Rank 0 additionally includes alternate recurrent banks and the full speculative private-image capacity, even when an individual capture copies only a KV suffix. No third bank, split head, compact vocabulary, V3 movement or compressed KV is assumed.

MTP adds exactly **4,193,685,814 bytes** on rank 0: 3,326,953,472 base weight bytes, the independent full 248,320-token Q6 head (839,321,600), and 27,410,742 bytes of plan/merge/workspace/control allocations. All draft plan buffers are included, including buffers whose launches are later removed. The historical 80,128-token head prefix is excluded. See the unchanged [draft ledger](draft-weight-accounting.json).

For 24/24 + MTP, rank 0 has 1,806 device allocations and rank 1 has 1,654. Rounding each allocation independently to 64 KiB would produce 30,793,596,928 and 29,744,037,888 bytes, leaving 1,418,657,792 and 2,468,216,832 bytes below 30 GiB. This is an **illustration, not an allocator guarantee**. The actual owner passes requested byte lengths to its backend; SYCL/driver reservations are not measured here. The default 22/26 rank 1 has only 246,826,892 logical bytes of headroom (169,213,952 in that illustration).

## Source status and limits

The latest source binds GSQ baseline selection defaults and conditionally skips static snapshot preparation for the production snapshot path. Those specific initialization concerns are resolved by source inspection; full Engine initialization remains unexecuted. An earlier concern about missing draft defaults was withdrawn after verifying that the inherited Selection already initializes them.

The 30 GiB arena limit and nominal 32 GiB card capacity are different from available physical memory. Driver contexts, queues, command lists, compiled kernels, allocation rounding/shadows and other owners are unknown. Runtime physical admission must independently check memory before loading either target or draft. The ledger is not a host RSS bound: file cache, metadata, prepared command vectors and transient conversion/upload storage are additional. Counted pinned host storage is 4,280,332 bytes on MTP rank 0 and 4,259,840 on rank 1; shared rank mapping adds 266,304 bytes once. No throughput, quality or native correctness claim follows from this forecast.

## Reproduction and retained authority

[engine-accounting.py](engine-accounting.py) evaluates the formulas and nine internal cross-checks under nice 19, helper cores and a 4 GiB address-space cap. [engine-accounting.json](engine-accounting.json) contains totals/categories for all six scenarios and full allocation details for the selected 24/24 + rank-0 MTP scenario, plus source hashes and all assumptions. [engine-accounting.sources.json](engine-accounting.sources.json) retains exact relevant source text so later private-build regeneration does not erase this forecast's authority. [engine-accounting.review.json](engine-accounting.review.json) binds the final artifacts and confirms the source hashes were current at closeout. No compiler or runtime is invoked by this script.

The full six-scenario generated ledger is retained under ignored `integration/build/memory-ledger-full.json`; its exact SHA and size are in the compact ledger. The pinned recipe reconstructs it. Removing repetitive allocation arrays from the tracked summary does not remove any fit uncertainty.
