# Attempt 6 CPU source audit: device budget

This audit reads checkpoint headers and source only. It does not measure device
allocations, graph capture, execution, or throughput. Paths under `V/` below mean
`/home/steve/src/lumnus-20261008/vllm/`; `R/` means this repository. Values use
GiB = 1,073,741,824 bytes.

## Resident-weight census

The old 29.55 GiB value was a **lower bound**, not a complete static allocation
bound. `memory_plan.py:395–421` divides almost all weights evenly by TP, retaining
only the known replicated HC matrices, and deliberately excludes scales and
biases. The following stronger planning census pessimistically replicates every
checkpoint tensor except these source-proven partitions:

- Expert weights: EP4, divide by four, including the MTP expert layer. The v5
  placement additionally removes exactly `4,915,200 = 3 * 2560 * 640` FP8 bytes
  per parked target expert; its scales remain device-resident.
- Input embedding and output head: TP4, divide by four. Shared target/MTP aliases
  count once. `V/vllm/models/qwen4_exp/nvidia/model.py:400,679`,
  `mtp.py:185,406` instantiate vocab-parallel embedding/head layers.
- GDN `in_proj_qkv`, `in_proj_z`, `out_proj`: TP4, divide by four. See
  `V/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py:431,496,559–586`
  for merged-column and row-parallel projections.
- QSA `q_proj`, `o_proj`: TP4, divide by four; `k_proj`, `v_proj`: divide by two.
  The two checkpoint KV heads are replicated across four ranks, so each rank
  stores one whole head. `V/vllm/models/qwen4_exp/nvidia/qsa.py:215–244`.
- Everything else is charged in full to each rank: HC, routers, shared experts,
  PLE projections, norms, scales, and even the full vision tower. This is
  deliberately pessimistic about sharded shared experts and the disabled image
  path. QSA indexer is genuinely replicated (`indexer_qsa.py:132`); PLE KV
  projection is replicated (`ple_layer.py:106–117`).

Exclude PLE table/metadata here because the mmap contract accounts separately
for its fixed cache, metadata and step buffers. Ignore only checkpoint
`hashstats_`/`token_lookup` auxiliaries. This remains a **tensor-storage planning
census**, not an upper bound on runtime buffers, repacks, alignment, or allocator
retention.

Reproduce without importing torch or accessing tensor payloads, from the reopen
directory:

```python
from collections import defaultdict
from memory_plan import DEFAULT_MODEL, read_metadata

config, tensors, metadata = read_metadata(DEFAULT_MODEL)
groups = defaultdict(int)
for name, tensor in tensors.items():
    if 'ngram_embedding' in name:
        continue
    if any(s in name for s in ('hashstats_', 'token_lookup')):
        continue
    size, group = tensor['bytes'], 'replicated_all_other'
    if '.experts.' in name and name.endswith('.weight'):
        size //= 4
        group = 'expert'
    elif ('embed_tokens' in name or 'lm_head' in name) and name.endswith('.weight'):
        size //= 4
        group = 'embed_head'
    elif any(s in name for s in (
        'linear_attn.in_proj_qkv.weight', 'linear_attn.in_proj_z.weight',
        'linear_attn.out_proj.weight', 'self_attn.q_proj.weight',
        'self_attn.o_proj.weight',
    )):
        size //= 4
        group = 'tp_attention'
    elif any(s in name for s in ('self_attn.k_proj.weight', 'self_attn.v_proj.weight')):
        size //= 2
        group = 'replicated_kv'
    groups[group] += size
print(dict(groups))
before_offload = sum(groups.values())
resident = before_offload - 317849600 - 2600 * 4915200
print(before_offload, resident, resident / 2**30)
```

Expected groups, in bytes per rank: replicated others 2,999,300,088; TP attention
1,344,798,720; expert weights 30,828,134,400; replicated KV projections 34,078,720;
embedding/head 635,699,200. Total before embedding/expert offload is
**35,842,011,128 bytes (33.380474083 GiB)**. With 2,600 host experts per rank,
expert host storage is **12,779,520,000 bytes (11.901855469 GiB)**; embedding host
storage is 317,849,600 bytes; resident-weight census becomes
**22,744,641,528 bytes (21.182598107 GiB)**. The old optimistic floor becomes
19.983603060 GiB; its correction is 1.198995046 GiB, conservatively rounded to
**1.25 GiB** in the planning budget.

## Context, activations and graph pools

Context capacity is 4,352, but activation batches contain at most **64 tokens**:
`V/vllm/v1/worker/gpu/model_runner.py:219–220` keeps `max_model_len` and
`max_num_tokens=max_num_batched_tokens` distinct. Do not size all activations as
4,352 rows. Context-dependent state is covered by the explicit full-precision
KV budget **376,569,856 bytes (0.350708008 GiB)** and runtime allowance; this
audit does not assert every recurrent-state allocation lies inside KV.

Representative source-derived buffer sizes:

- Triton MoE workspaces (`experts/triton_moe.py:218–233`) each use
  `[M,topk,max(width,K)]`. With M=64, topk=10, K=2560 and FP16-family intermediates,
  the pair is 6,553,600 bytes; output `[64,2560]` is 327,680 bytes. If EP's
  all-gather route expands M to 256, the pair and output total 27,525,120 bytes.
- Target MTP hidden buffer is `[64,4*2560]` BF16 = 1,310,720 bytes
  (`model.py:453–457`).
- QSA packed selection has width `2048+4=2052`, not 4,352:
  `indexer_qsa.py:183–196`, `qsa.py:315–330`. Each `[64,2052]` INT32 buffer is
  525,312 bytes, about 6.51 MiB for 12 target QSA layers plus one MTP layer.
- QSA FP32 split output/LSE is `[splits,M,6,256]` plus `[splits,M,6]`;
  `ops/qsa.py:442–474,548–554` chooses 8 splits at M=64 and up to 64 at M<=24.
  M=64 needs 3,158,016 bytes; the larger intermediate shape M=24/splits=64 needs
  9,474,048 bytes. They are temporary per invocation, not multiplied by all
  model layers as simultaneously live eager activations.
- PLE's stable device step contains `64*16*160 = 163,840` FP8 bytes; its host
  twin and the 1 GiB/rank host cache are host accounting, not extra VRAM.

A **0.5 GiB activation/workspace allowance**, **0.5 GiB graph-pool allowance**
for capture sizes [1,2], and **0.75 GiB runtime/allocator allowance** are planning
reserves. They are not measured, source-proven full upper bounds or admission
evidence. Rotary caches, temporary conversion/quantization buffers, recurrent
scratch, and backend retention are reasons to keep reserves beyond the named
small tensors. Graph lifetimes require a real capture receipt.

Using the optimistic floor plus rounded 1.25 GiB static correction, KV, the
0.5+0.5+0.75 GiB allowances, and PLE device step gives an engine scenario of
**23.334463656 GiB per rank**. Relative to 30.3 GiB total at utilization 0.90,
this leaves about 3.9355 GiB inside the 27.27 GiB requested engine budget.
Relative to attempt-5 free memory 27.65 / 27.87 GiB, it leaves about
**4.3155 / 4.5355 GiB driver-usable free**, conditional on the initialization footprint
and all allowances holding. Do not add the initialization occupancy inside the
engine budget and then subtract it from observed free memory a second time.

## Expected cost of additional parked experts

`R/experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md:202`
reports approximately **0.1 ms per selected host expert**. Its receipt is
`data/20260905-b70-moe-expert-placement-equivalence-timing.txt`: in the half-host
layout, three host hits change combined w13+w2 time from 0.5276 to 0.8225 ms,
or **0.0983 ms per hit**. Resident-only control comparisons have a different
baseline; this is a sensitivity estimate, not a universal transport constant.

Use `extra_step_ms ≈ 0.1 * extra_selected_host_experts_on_critical_rank`.
For an explicitly hypothetical uniform routing model, additional parked rows
`D` on one rank imply `10*D/512` extra hits across 48 target layers per target
token, or about `D/512` ms. A two-row MTP verifier can approximately double
this term if its two rows select distinct work. This is not an output-token
throughput forecast: routing, reuse, overlap, MTP acceptance and rank imbalance
are unmeasured in V30. Do not normalize the saved A315 census with a partial
log's step count.

The subsequent matched A314 endpoint result explicitly limits this extrapolation:
`notes/2026-09-07-a314-negative-host-placed-selections-cost-nothing.md` reduced
the hot-rank parked selection rate from 12.410% to 0.048%, but mean throughput
changed only -0.021 tok/s. Its proposed page-migration explanation is an
inference, not a measured driver mechanism. Therefore neither the microbenchmark
tax nor the endpoint's near-zero change certifies attempt-6 performance,
especially after changing driver backing settings and total offload size.
