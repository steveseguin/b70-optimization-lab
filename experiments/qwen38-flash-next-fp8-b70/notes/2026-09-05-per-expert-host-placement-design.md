# Per-expert host placement for free VRAM headroom (design, 2026-09-05)

## Why

The headroom lines (A179-A190) end the xe driver's VRAM paging by host-offloading whole
expert-weight tensors of the first layers through UVA (`mlp.experts` under a budget). Every
offloaded layer then reads its 10 routed experts over PCIe on every step: ~1 ms per layer,
~2.7 ms of the 37 ms MTP0 step, and the MTP1 line needs more headroom than MTP0 (A191).
The A168 census shows that on a trajectory 58% of (layer, expert) pairs are never routed to
and the coldest 40% of experts per layer receive 0.00% of hits. Host-resident *cold experts*
give the same headroom at essentially zero decode cost, and more headroom is free.

## Mechanism (bit-exact by construction)

- After weight loading, for each MoE layer split `w13_weight`/`w2_weight` [E_local, N, K] into
  a resident device tensor (rows of hot experts) and a pinned host tensor (rows of cold experts)
  exposed as a UVA view; free the original. Block scales stay on the device in full (tiny).
- Build one int64 table per weight, `base[e] = address of row e` (device or UVA), and pass it
  to the Triton kernel instead of `b_ptr`. The kernel computes
  `b_base = tl.load(table + off_experts).to(pointer)` and everything else is unchanged:
  same tiles, same K loop, same accumulation order, same scale indexing by `off_experts`.
  A row is computed by exactly the same code reading exactly the same bytes, so outputs are
  bit-identical to the resident layout; only the address a row lives at changes.
- Placement input: a JSON `{layer_idx: [local expert ids]}` produced from the top-k censuses
  (A168 2K trajectory, A195 realistic suite; union of hits, never-hit experts eligible),
  capped at the headroom target per rank (e.g. 2.0 GiB = ~420 of 6,144 experts per rank).
- Fallback cost model: a cold expert that does get hit costs one PCIe read of its 4.9 MB
  (~0.3 ms), the same as today's whole-layer offload for that expert, so the worst case
  degrades gracefully instead of paging.

## What it touches

`vllm/model_executor/layers/fused_moe/fused_moe.py` (kernel: optional base table; invoke:
pass table), a new `vllm/q38_expert_placement.py` (split + tables + UVA views, env
`Q38_EXPERT_HOST_PLACEMENT=<json>`), and the FP8 MoE post-load hook to call the split.
Because `fused_moe.py` is part of the W13-N32 verifier's source contract, a promotion needs
a new accepted head with a re-oracle (as 1b2a17c1 was added for the MTP1 selectors).

## Screening plan

1. Offline: confirm the int64→pointer cast on the XPU Triton build and equivalence of the
   table path against the resident path on random weights (bit-exact), plus timing with the
   cold rows in host memory.
2. A196: the A179 identity with `Q38_EXPERT_HOST_PLACEMENT` and *no* `mlp.experts` offload;
   hash must stay `afffd211…`, step should drop by the PCIe share (~2.7 ms).
3. MTP1 with the same placement (more free headroom than the 13.4 budget gives today).
