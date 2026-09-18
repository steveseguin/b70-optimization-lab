# Two-card exchange fusion: where the cross-card traffic is, what it costs, and what is left (2026-09-18)

Research memo, no GPU work. Sources: the shipped two-card package
([`packages/qwen38-27b-fp8-tp2-b70/compose.yaml`](../../../packages/qwen38-27b-fp8-tp2-b70/compose.yaml)), the model
code read out of the `r312d-c` image (`/opt/venv/lib/python3.12/site-packages/vllm/...`, vLLM 0.29.0; the tp2 package
pins image `sha256:eb81650704…` = R310 of the same 0.29.0 lineage, `compose.yaml:7`), and a fresh re-analysis of the
September 17 two-card decode trace
`/mnt/fast-ai/bench-results/fp8-profile4-20260917/tp2-profile-trace/worker-rank0-pid252.json` (212 MB, kept on disk;
the summary in [`../data/2026-09-17-fp8-night3/tp2-decode-profile-summary.json`](../data/2026-09-17-fp8-night3/tp2-decode-profile-summary.json)
is a top-kernel roll-up of it). The starting point is
[`2026-09-16-fp8-review-findings.md`](2026-09-16-fp8-review-findings.md) lines 175-196 (decode profile), 197-215
(comm-2), 260-291 (comm-3/comm-4) and 678-684 (the open exchange-fusion idea).

**Headline: the premise needs correcting before any fusion work starts.** The review note's "the allreduce is 47% of
device time, 30 ms per step" is a rank-skew artifact of a trace in which *both* ranks were profiled. The median
allreduce kernel on this host is **10.8 µs**, not 223 µs, and the whole per-step collective bill is **~1.2 ms of
device time out of a ~33 ms step**. The +2.3% that comm-2 actually measured is exactly what halving 1.2 ms predicts.
So per-layer exchange *fusion* has a ceiling of roughly 2%, and the cost that remains is per *call*, not per byte.

---

## 1. Where the cross-card exchanges are

Model: `Qwen3_5ForConditionalGeneration` → text config `qwen3_5_text`, **not** a MoE text config
(`/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/config.json`: `model_type: qwen3_5_text`, `hidden_size 5120`,
`num_hidden_layers 64`, `full_attention_interval 4` → 48 `linear_attention` + 16 `full_attention` layers,
`vocab_size 248320`, `mtp_num_hidden_layers 1`). Served `--dtype float16 --tensor-parallel-size 2`, MTP depth 5
(`compose.yaml:212-215, 234`).

### Per decoder layer (all 64, both layer types)

| Site | Code | Collective |
| --- | --- | --- |
| attention out-projection | `qwen3_next.py:316-322` (`o_proj = RowParallelLinear(..., reduce_results=True)`), forward `qwen3_next.py:446-457`; the GDN layer's `out_proj` takes the same `reduce_results` from `qwen3_5.py:150` | `tensor_model_parallel_all_reduce`, via `linear.py:1766-1767` |
| MLP down-projection | `Qwen3NextMLP` (dense; `qwen3_5.py:172-178`), `down_proj` row-parallel | same |

`reduce_results` is `not self.use_attn_reduce_scatter_for_moe` (`qwen3_5.py:150, 159`), and that flag is
`parallel_config.use_sequence_parallel_moe and pp==1 and is_moe_layer` (`qwen3_5.py:138-141`) — with
`model_type == qwen3_5_text` it is **False for every layer**. The sequence-parallel reduce-scatter path in
`qwen3_next.py:561-562` and `585-591` is therefore dead code on this model. So: **2 all-reduces per decoder layer,
128 per target forward.**

### Per step, whole picture

The trace gives the exact schedule. Every collective carries a `record_param_comms` event with `In msg nelems`, so
call count *and* payload are directly readable. Segmenting the trace on the verify-logits all-gather gives **26 clean
decode steps, each with exactly 155 collectives** (the 27th window contains a prefill):

```
target/verify pass, 6 rows (1 bonus + 5 drafts):
    1 x all_reduce  6x5120  = 30720 half   VocabParallelEmbedding (vocab_parallel_embedding.py:714/718)
  128 x all_reduce  6x5120  = 30720 half   64 layers x (o_proj, down_proj)
    1 x all_gather  6x124160                ParallelLMHead logits, vocab/2 per rank (qwen3_5.py:347)
MTP draft pass 1, 6 rows:
    1 x all_reduce  6x5120                  MTP embed_tokens (qwen3_5_mtp.py:84-87)
    1 x all_gather  6x2560                  fc, ColumnParallelLinear(gather_output=True) (qwen3_5_mtp.py:98-106)
    2 x all_reduce  6x5120                  MTP layer o_proj + down_proj (layer_type="full_attention", qwen3_5_mtp.py:118-125)
    1 x all_gather  1x124160                draft logits (only the last row is sampled)
MTP draft passes 2-5, 1 row each (x4):
    3 x all_reduce  1x5120                  embed_tokens, o_proj, down_proj
    1 x all_gather  1x2560                  fc
    1 x all_gather  1x124160                draft logits
```

Totals per step: **144 all-reduce** (132 at 30720 elems = 60 KB, 12 at 5120 elems = 10 KB) and **11 all-gather**
(1x744960, 1x15360, 5x124160, 4x2560), = 155 collectives. The MTP drafter's forward is
`qwen3_5_mtp.py:146-190`; its five passes are strictly sequential (pass *k+1* embeds the token pass *k* sampled).

Correction to the review note: it read "134 allreduce calls per step" as 4017/30. The trace holds 26 decode steps
plus one prefill (132 all-reduces at 78x5120), so the true decode figure is **144 per step**, not 134.

### The transport

`XpuCommunicator.all_reduce` (`xpu_communicator.py:48-52`) is

```python
output = input_.clone()
work = dist.all_reduce(output, group=self.device_group, async_op=True)
work.wait()
```

— i.e. a full-size D2D copy per call (the trace's 5740 `Memcpy D2D`, ~191 per step) plus a oneCCL PCIe ring
all-reduce, immediately waited on. The shipped overlay
[`b70_allgather_allreduce.py:27-46`](../overlays/b70-allgather-allreduce/b70_allgather_allreduce.py) replaces this for
world size 2 with `all_gather_into_tensor` + `gathered[0] + gathered[1]`: it drops the clone and swaps the ring kernel
for an all-gather kernel plus one elementwise add. Same call count.

---

## 2. What the exchange actually costs

Re-derived from the trace (order-matched `record_param_comms` payloads against `oneccl_*_pcie` kernel durations):

| Collective | nelems | calls in trace | mean kernel | **median kernel** | p10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| all_reduce | 30720 | 3561 | 218.6 µs | **10.8 µs** | 8.2 µs |
| all_reduce | 5120 | 324 | 311.6 µs | 182.1 µs | 7.9 µs |
| all_reduce | 399360 (prefill) | 132 | 124.5 µs | 32.3 µs | 26.6 µs |
| all_gather | 124160 | 136 | 55.1 µs | 40.6 µs | 9.0 µs |
| all_gather | 744960 | 27 | 170.4 µs | 52.5 µs | 42.9 µs |

The 223 µs mean quoted in the review note is the mean of a wildly bimodal distribution (1999 of 4017 calls under
25 µs; a second lobe at 525-650 µs). The long lobe is *waiting for the peer rank*, and the reason is visible per
step: summing collective device time inside each step window alternates **14 ms, 53 ms, 14 ms, 53 ms…** across
consecutive steps, and one step in the trace (a lockstep one) shows all 132 target-pass all-reduces at 8.2-9.8 µs
each — **1.11 ms for the entire target forward's exchanges**.

Why the ranks ping-pong: the campaign asked for a single-rank trace
(`../scripts/run-20260917-fp8-profile4-campaign.py:80` sets `B70_PROFILE_RANKS=0`) but **both ranks profiled anyway**.
The gate at [`b70_step_profiler.py:27-35`](../overlays/b70-step-profiler/b70_step_profiler.py) runs at plugin
registration, before the TP group exists, so `get_tensor_model_parallel_rank()` raises and it falls back to
`RANK`/`LOCAL_RANK`, unset in vLLM's spawned XPU workers → both workers resolve to rank 0 and both profile. (The
export path at line 100-105 re-queries the rank, by then correctly, which is why two differently-named files exist.)
Two profiled processes inflate the step from ~30 ms to 103.6 ms (`*.meta.json`: 30 steps in 3.109 s) and generate the
skew. **This is a one-line overlay bug and it invalidated the cost attribution in the review note.**

Sanity check against measured speed: no-MTP two-card is 33.86 tok/s → 29.5 ms/step; depth-5 is 90.37 tok/s at roughly
3 accepted tokens/step → ~33 ms/step. Comm-2 replaced the ring all-reduce (median 10.8 µs) with an all-gather
(median ~9-40 µs) plus an add and won **+2.3%** = ~0.76 ms/step. That matches a ~1.2-1.5 ms/step collective budget
almost exactly. It does **not** match a 30 ms/step budget, which would have predicted ~25% — which is precisely the
discrepancy the review note flagged at line 212 and attributed to synchronisation. It is not synchronisation; the
measurement was wrong.

The other term is host-side. `c10d::allreduce_` cpu_op duration: n=4017, **median 99.7 µs**, of which
`xccl:all_reduce` is 82.1 µs; `c10d::_allgather_base_` median 93.9 µs. Per profiled step that is 15-19 ms of host
time (15-16% of the profiled wall) issuing 155 collectives, and it is steady across fast and slow steps. Deflating
by the 3.4x profiler inflation puts the real dispatch cost near **~30 µs per collective, ~4.5 ms per step** — three
to four times the device cost and the actual reason exchanges are expensive here.

**Ceiling for any lossless fusion: ~0.6-0.7 ms/step of remaining device time (≈2%) plus whatever share of the ~4.5 ms
host dispatch a reduced call count can remove.** Nothing in this lane can be worth 10%.

---

## 3. Candidate fusions

### (a) Sequence-parallel: replace allreduce(o_proj) + allreduce(down_proj) with reduce-scatter/all-gather — **no-go**

The residual-order objection is actually *not* the problem. Megatron-style SP keeps the two-operand sum per output
row (`reduce_scatter` on 2 ranks computes `x_r0[shard] + x_r1[shard]`, the same two-operand add), and the residual
add and RMSNorm are per-row, so row sharding preserves them bitwise. Two real objections kill it instead:

1. **No call-count reduction.** SP replaces 2 all-reduces per layer with 1 reduce-scatter + 1 all-gather per layer:
   still 128 collectives per target forward, half the bytes each. With bytes costing ~10 µs and calls costing ~30 µs
   of host dispatch, expected gain ≈ 0.
2. **It changes GEMM M.** `sp_pad = (-shape[0]) % tp_world_size` then shard (`qwen3_next.py:586-591`) takes the MLP
   from M=6 rows to M=3 (and draft passes from M=1 to a padded M=1). This lane's oneDNN W8A16 path is
   M-class-sensitive — the whole `VLLM_XPU_FP16_LINEAR_CLASSPAD` / class-pad work exists because of it — so the GEMM
   result is *not* guaranteed bit-identical across an M change. That is a gate failure waiting to happen.
3. Mechanically it does not even run: `_should_use_sequence_parallel` requires `num_experts > 0`
   (`qwen3_next.py:84-94`) and the SP branch calls `self.mlp(hidden_states, already_sequence_parallel=True)`
   (`qwen3_next.py:595-598`), a kwarg the dense `Qwen3NextMLP` does not accept. Enabling it needs model surgery, not
   a flag.

Effort high, risk high, expected gain zero. **Drop.**

### (b) Batch the MTP draft passes' all-gathers into one exchange — **not available**

Dependency analysis of `qwen3_5_mtp.py:146-190`: within a draft pass, `embed_tokens` → all-reduce →
`pre_fc_norm_embedding` (needs the full reduced row) → `cat` → `fc` → all-gather (needs the full 5120 row for the
layer's `input_layernorm`) → layer → o_proj all-reduce → down_proj all-reduce → logits all-gather. Every edge is a
true data dependency. Across passes, pass *k+1*'s `input_ids` is pass *k*'s argmax. Nothing to batch. The same holds
inside the target forward. At batch 1 there are no independent exchanges in a step at all. **Closed.**

### (c) Overlap the exchange with the next GEMM on a second queue — **already tested, neutral**

`dist.all_reduce(..., async_op=True)` is already used and the `work.wait()` at `xpu_communicator.py:51` is the only
thing serialising it. **R207 already removed that wait** (`docker/r207-allreduce-no-host-wait.py`,
`VLLM_XPU_ALLREDUCE_HOST_WAIT=0`): MTP1 55.22/55.11 tok/s, depth 4 82.61/82.74, all 12/12 — lossless and within
noise (see [`2026-09-04-qwen38-fp8-r187-decode-profile-r199c-result.md`](2026-09-04-qwen38-fp8-r187-decode-profile-r199c-result.md)
lines 49-57). The conclusion there still stands: the wait is a stream-level dependency at most. And the dependency is
genuine anyway — the very next op after each all-reduce consumes its output. There is no independent GEMM to hide it
behind at batch 1. Note the shipped recipe pins `VLLM_XPU_ALLREDUCE_HOST_WAIT=1` (`compose.yaml:57`), the setting the
A/B found neutral. **Closed.**

### (d) Skip the exchange in the draft passes by replicating the drafter — **tested, negative, and it does not carry**

Comm-3/comm-4 (review note lines 260-291): replicating all drafter parts cost -4%; head only -0.4%; embedding+fc -1%.
The reason is visible in the payload table above: the drafter's exchanges are the *cheapest* in the step (12 calls at
10 KB and 9 all-gathers), while replication makes each rank do the full unsharded 248320x5120 embedding gather and a
doubled MLP GEMM. It does not carry over to the target layers either: those 128 all-reduces cannot be removed by
replication without replicating the whole 27B model per card, which does not fit. **Closed** — and it is the cleanest
empirical proof that the cost here is per call, not per byte. The same point is made independently by
[`2026-08-16-q8-distributed-greedy-argmax-neutral.md`](2026-08-16-q8-distributed-greedy-argmax-neutral.md): shrinking
a logits collective's payload to two scalars was neutral.

### (e) Fuse the `gathered[0] + gathered[1]` add into the following add+RMSNorm — **the only live candidate**

Today each exchange costs two device kernels: the `all_gather_into_tensor` and a separate elementwise add
(`b70_allgather_allreduce.py:44`), plus a fresh `torch.empty((2,)+shape)` per call. The add's result then goes
straight into `post_attention_layernorm(hidden_states, residual)` / the next layer's `input_layernorm`, which on this
build is the Triton fused kernel `triton_red_fused__to_copy_add_fp8_gemm_w8a16_fused_add_rms_norm_t_*` (868-1003
launches in the trace). Computing `(g0 + g1) + residual` inside that kernel is **bit-identical** as long as the
association is left-to-right in exactly that order, which is what the two ops do today: `(g0+g1)` first, then
`+residual`. Both ranks compute the same thing in the same rank order, so the comm-2 exactness argument carries
unchanged.

What it buys: 144 fewer kernel launches and 144 fewer allocations per step. At the trace's ~2.3-2.6 µs for these
pointwise kernels that is ~0.37 ms of device time, plus the host launch cost, against a ~33 ms step: **expect
1-2%**, i.e. 91.3-92.2 tok/s. Risk: moderate — it has to be hooked at the decoder-layer boundary (the communicator
cannot see the residual), so the overlay must wrap `Qwen3_5DecoderLayer.forward`, which is where the September 17
GDN-checkpoint campaign learned the model class must be resolved through the registry, not by name
(review note lines 231-235). Effort: 1-2 days, no kernel rebuild if the fused add is written in Triton on top of the
existing norm.

A cheaper sibling worth folding into the same overlay, zero arithmetic change by construction: **pre-allocate the
gather buffer per (shape, dtype)** instead of `torch.empty` per call. There are only four shapes in a steady decode
step (6x5120, 1x5120, and the two prefill/ladder shapes), so a small dict of persistent buffers removes 155
allocations per step for free.

---

## 4. Recommendation

**Do the measurement fix first — it is free and everything else depends on it.**

1. **Fix `b70-step-profiler`'s rank gate** (`b70_step_profiler.py:27-35`): move the rank check out of `register()`
   into the wrapped `execute_model`, where the TP group exists. One-line-class change, no GPU work to write it.
   **Done 2026-09-18**: the rank is now resolved on the first `execute_model` call (tensor-parallel group, then
   the runner's `rank`/`local_rank`, then `$RANK`/`$LOCAL_RANK`) and logged once;
   `tests/test_b70_step_profiler_rank_gate.py` covers the gate with a stubbed `parallel_state` (no GPU). Traces
   taken before this date carry both ranks.
2. **Re-profile two cards with one rank only**, with the shipped allgather overlay on (profile4 predates comm-2 and
   traced the stock ring). That gives the first uncontaminated two-card step budget: device busy, idle gaps, real
   per-collective device and host cost. Until this exists, every "N% of device time" number for two cards is
   unusable.

**Then the single experiment: comm-5, overlay `b70-fused-gathered-add`.**

- **What:** extend the allgather overlay with (i) persistent per-shape gather buffers and (ii) a fused
  `(g0 + g1) + residual` + RMSNorm kernel, installed by wrapping `Qwen3_5DecoderLayer.forward` on every class the
  registry resolves (target layers and `qwen3_5_mtp`'s layer), falling back to the current two-op path for any shape
  or call site it does not recognise.
- **Env flag:** `B70_FUSED_GATHERED_ADD=1`, layered on top of `B70_ALLGATHER_ALLREDUCE=1` (which stays the transport).
  Keep it a separate flag so a failed gate is one env var away from the shipped behaviour.
- **Gates** (identical to comm-2, `../scripts/run-20260917-fp8-comm2-campaign.py`): a same-session no-MTP reference
  under the same overlay; strict 12/12 twice against it; the 64/64 + queued ladder; 2K/8K/16K prefill continuations;
  chat-quality and logprob-replay screens; two strict performance runs against the 90.3-90.6 tok/s allgather control.
- **Go/no-go:** ship only if both strict runs are **12/12** *and* the median of the two is **≥ 91.3 tok/s (+1.0%)**.
  Below +1.0%, or any single non-exact gate, close it and stop the two-card fusion lane: the ceiling established in
  section 2 leaves nothing else on this axis worth a kernel project.
- **Do not** run this on a boot that has already faulted; the September 16-17 sequence put three faults on one boot
  and the service is still gated on the user's reset decision (review note lines 192, 670).

**What to stop doing.** Sequence-parallel (a), draft-pass batching (b), async overlap (c) and drafter replication (d)
are all closed by the analysis or by an existing measurement. If comm-5 lands under +1.0%, the honest position is
that the two-card lane is finished at ~90.4 tok/s and the remaining headroom is on the four-card replay, not on the
exchanges.
