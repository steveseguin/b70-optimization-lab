# DeepSeek V4.1 Flash on our engine: why the load froze the host, and first correct decode on cards

2026-11-09, `steve-TURIND8-2L2T` (now **six** Arc Pro B70, still 15 GiB of host RAM), kernel 7.0.0-38,
oneAPI 2026.1. Model: Unsloth `DeepSeek-V4.1-Flash-1017-GGUF` UD-IQ2_XXS (165.3 GB backbone + 135.2 GB Q5_K
engram table on NVMe). Lane: `engine/` (Own Xe), family `dsv41`.

## Outcome in plain words

- The machine froze four times because **card memory was landing in ordinary RAM**. Two causes, both measured,
  both fixed in the loader. Loading 109 GB onto four cards now takes 12 seconds and host free memory does not move.
- The device decode had never run. It had real bugs, and so did the CPU reference it was to be checked against.
  The reference is now checked **layer by layer against llama.cpp** (all 40 layers and the output agree within
  llama.cpp's own rounding), and the cards match the reference on every layer and on the output tokens.
- **The whole model runs on all six cards** (owner stopped and disabled the Gemma service at about 17:05 EST):
  165.3 GB loaded in 20 s with host free memory flat, a complete correct answer. With f32 activations (default
  since 17:30) all 40 tokens of the test equal the CPU reference. Sections 7 and 8.
- Speed: 0.111 s per token on six cards (9.0 tok/s), from 0.86 s when it first ran. The llama.cpp reference
  screen is 14 tok/s. Sections 6, 7 and 9.
- **Later the same evening: 60 tok/s, output byte-identical** (owner's goal was 25). New kernels and packed
  weights (28-31 tok/s, section 11), every layer split across all six cards (47-52, section 12), and a driver
  lock that made the six host threads wait on each other removed (60, section 13).

## 1. The freezes

Every freeze is the same kernel record: host out of memory with `[TTM] Buffer eviction failed`, anonymous and
page-cache pages near zero, swap almost unused. The missing RAM was graphics-driver pages.

**Cause A: a shared multi-card SYCL context costs host RAM 1:1.** Measured with `engine/tools/xe_vram_probe.cpp`
(steps of 512 MiB on an empty card, watching `MemAvailable` and this process's `/proc/self/fdinfo`):

| Context | On the card | Host `MemAvailable` change |
| --- | --- | --- |
| all six cards (`sycl::context(devs)`, also DPC++'s default for `sycl::queue q(dev)`) | 0.5 GiB | -515 MiB |
| same | 1.0 GiB | -1023 MiB |
| one card (`sycl::context(dev)`) | 6 GiB | -14 MiB |
| one card | 28 GiB (14 x 2 GiB) | -56 MiB |
| one card, single 8 GiB allocation, written | 8 GiB | -17 MiB |

A 154 GiB model in one shared context asks the 15 GiB host for 154 GiB. The old backend used one context over all
cards. (Same family as the September torch finding fixed by `expandable_segments`.)

**Cause B: xe does not fail an allocation that does not fit; it evicts into host RAM.** The kernel trace of the
"3 GiB allocation fails" probe is `xe_vm_bind_ioctl -> ttm_bo_validate -> ttm_bo_evict -> ttm_tt_populate`: binding
new memory on a full card evicted other buffers to system pages. The card was full because the Gemma service
(`gemma4-26b-q8-quad-backends`, enabled, restarts at boot) holds 29.8 GiB on `0000:03:00.0` and `0000:23:00.0`.
So the earlier conclusions "single allocations above 2 GiB fail" and "4 GiB wedges the driver" were wrong: those
probes were displacing Gemma's memory. "Allocate until it fails" can never be used on this driver.

Each opened card also costs about 185-200 MiB of host RAM per process (six cards: ~1.2 GiB).

**Loader rules now in `engine/src/stage2/packet3/backend/backend_sycl_v41.hpp`:**

1. One SYCL context per card. No device-to-device copies (already host-staged).
2. Read each card's free memory first (`ZES_ENABLE_SYSMAN=1`, `ext::intel::info::device::free_memory`; works
   without privileges and sees other processes). Refuse to start if a card is in use or lacks the bytes.
3. Exact-size arenas in <= 2 GiB pieces; host `MemAvailable` checked between allocations.
4. Upload disk -> 32 MiB staging buffer -> card (`O_DIRECT`, one thread per card), aborting below a
   `MemAvailable` floor (default 3072 MiB, `OWN_HOST_FLOOR_MIB`). No big pinned host mappings.

Result: 108.8 GB (layers 0-27) on four cards in 12.3 s at 8.9-9.6 GB/s; `MemAvailable` 13.21-13.24 GiB throughout;
no kernel fault line. 56.5 GB (layers 28-39 + head) on two cards in 5.9 s.

## 2. Bugs in the device decode (it had only ever compiled)

| Bug | Effect | Fix |
| --- | --- | --- |
| One attention window ring per card, shared by every layer on it | every layer overwrote the others' window | one ring per layer |
| `attn_output_a` read as BF16 | it is Q8_0 (27 layers) / Q6_K (13) in this GGUF | `GemvGroupedQ` decodes the real type |
| `Swiglu{n}` left the clamp limit at 0 | every MoE and shared-expert output zero | limit passed (10) |
| Expert down-projection read slot 0's activations for all six slots | wrong MoE output | `RoutedGemv.per_slot_x` |
| Scratch allocated lazily, state loaded before it | null-pointer writes | allocated in the constructor |
| Router logits rounded to BF16 | top-6 can flip on near ties | f32 logits + `RouteF32` (official routes in F32) |
| `WindowAppend` at `pos % 128 == 127` indexed slot 128 | reads a compressed row as a window row | wrap to slot 0 (host anchor too) |
| Sub-group kernels launched without a required sub-group size | lane reductions depend on the compiler's SIMD choice | `reqd_sub_group_size(32)` |
| Host top-k could pick the same index twice when scores are -inf | duplicate rows | sort with a total order |

## 3. Bugs in the CPU reference (`cpu_run_v41.cpp`), found against official `model.py` and llama.cpp

The README called this runner "validated" on four matching tokens. Four structural errors:

| Bug | Official / llama.cpp | Evidence |
| --- | --- | --- |
| FFN input collapsed with the FFN's own pre-mix | `Block.forward`: the FFN uses the pre-mix **the attention computed**; `deepseek41.cpp` `build_hc_pre(inpL, attn_mix.pre)` | source |
| `hc_post` used `comb[dst][src]` | `y[dst] = post[dst]*x + sum_src comb[src][dst]*residual[src]` | source; also in `ops_v41.hpp` and the SYCL `HcPost` |
| Prompt pass let even positions see one compressed row too many (`t/r + 1`), a row containing the next token | `compress_lens = arange(1, seqlen+1) // ratio` | llama dump: layer 2 attention off by 29 % before, 0.6 % after |
| Layers 37-39 treated as ratio 0 (window only, base rope) | `config.json` has 43 ratios: 40 layers (0,0, 2x18, **1x20**) + three zeros for DSpark | llama dump: only layers 37-39 failed the isolated check |

Smaller: candidate-block pin is inside the 2048 budget (official `select_candidate_blocks`); deterministic tie order
in top-k; a data race on the small-weight cache inside an OpenMP region that hung one run.

## 4. How the reference was checked against llama.cpp

`engine/tools/dsv41_llama_dump.cpp` (out of tree; built against `~/src/llama.cpp-dsv41-20261108/build-cpu`,
llama.cpp sources untouched) writes every named graph tensor for the 36-token prompt. `cpu_run_v41` with
`OWN_PDUMP` writes the same names. Two comparisons (`engine/tools/dsv41_llama_diff.py`):

- **Free running:** layers 0-3 agree to < 1 %; later layers drift slowly because llama.cpp's CPU backend
  quantizes activations to 8 bits inside quantized matmuls and near-tie expert choices flip.
- **Each layer in isolation** (`OWN_LLAMA_INJECT`: our layer gets llama.cpp's own input): **no tensor over 4 %
  (per-token median) on any of the 40 layers or the head**; final logit gaps top-3: llama.cpp 0 / 0.31 / 2.46,
  ours 0 / 0.26 / 2.45. `data/dsv41-bringup-20261109/llama-per-layer-teacher-forced.txt`.

End to end, forced along llama.cpp's own first nine tokens, our reference picks the same token at 8 of 9
positions; the ninth is a near tie (llama.cpp +0.38 for " asks", ours +0.22 for " wants"). Largest gap difference
among candidates within 8 logits of the top: 0.99. Our greedy text therefore leaves llama.cpp's at the third token.
This is agreement within llama.cpp's arithmetic noise, **not** a bit-level identity claim, and llama.cpp's saved
answer pack was made with a q8_0 KV cache. The reference's own prompt pass and step-by-step pass agree exactly
(same top-5 logits to four decimals at step 6).

## 5. Device against the reference

Trace gate: `cpu_run_v41` (`OWN_TRACE`) and `own_run_v41` (`OWN_TRACE`) write the same tagged records per decode
step; `engine/tools/dsv41_trace_diff.py` compares them.

| Run | Cards | Result |
| --- | --- | --- |
| layers 0-27, 3 steps, teacher-forced tokens | 43, 83, a3, e3 | 1599 records, none over 5 %; block outputs within 0.35-1.3 % |
| layers 28-39 + head, reference streams injected at layer 28 | 43, 83 | 690 records, none over 5 %; tokens 3967, 10059, 260 = reference; top logit 34.396 vs 34.452 |

The ~1 % is the activation format: device buffers are BF16 between operators (as the official model runs), the
reference is f32. An f32-activation mode is open work if exactness against the reference is wanted.

Timing when it first ran (per-op sync, host top-k): 0.60 s for layers 0-27, 0.26 s for layers 28-39 + head.

## 6. First speed round (same day)

`OWN_PROF=1` prints time per operation group. Every change below left the decode trace **byte-identical** to the
run before it, except the stream-mix statistic, whose reduction order was redefined (host anchor and device
agree exactly; trace gate against the reference unchanged).

| Change | Layers 0-27, ms per token |
| --- | --- |
| as first run | 629 (profiled) / 600 |
| attention core in three launches (per head x slot scores, per-head softmax, per head x channel output) instead of 64 long serial work-items | 448 |
| stream-mix statistics as 32 strided lanes + tree in double (`ops41::hc_mix_lanes`) instead of 24 serial 20480-term loops | 324 (profiled) |
| one gemv kernel per weight format (`GemvT`, `RoutedGemvT`, `GemvGroupedQT`): the format no longer is re-selected per element | 225 (profiled) |
| expert kernel takes slot and row from the **group** id, so the row address is uniform across the 32 lanes (it was a per-lane gather) | 111 (profiled) / **103** |

Tried and worth nothing here: chunk-indexed lane loop (-5 %), byte loads instead of 64-bit variable shifts for the
64-bit grid formats (0 %; kept, bit-exact, gated as `decode_fast_*`).

Now: layers 0-27 in 0.103 s, layers 28-39 + head in 0.059 s, 0.16 s per token, about 6 tok/s. Remaining time on
layers 0-27 (profiled, ms): expert down 19, stream mix 13, expert gate 10 + up 10, router 9, engram 8 (mostly cold
4 KiB reads of the 24 hashed rows from NVMe), attention core 7, shared expert 6, output LoRA b 6 + a 4, query 5.
Not launch overhead: the profile's 1,260 queue waits add only 8 ms.
Evidence: `data/dsv41-bringup-20261109/profile-layers0-27-round{0,1}.txt`, `device-speed-*.log`.

## 7. Six cards, whole model (17:07 EST)

| | |
| --- | --- |
| Load | 165.3 GB in 19.7 s and 20.2 s (8.2-8.4 GB/s); `MemAvailable` 13.1 GiB before, during and after; 5.0-7.0 GiB left free per card; no kernel fault line |
| Output | `The user wants a simple greeting in one sentence. I should respond with a friendly hello in exactly one sentence. Keep it brief and warm.</think>Hello! It's nice to meet you, and I'm here to help with whatever you need.<EOS>` |
| Against the CPU reference | tokens 1-26 equal; token 27 is " warm" (device) vs " natural" (reference), a 0.39-logit margin in the reference |
| Trace gate, 3 steps, 2289 records | steps 1 and 3 clean; step 2 has one expert choice that differs at layer 36 (sixth of six, a near tie), which lifts four later records to 5.0-5.7 %; same argmax |
| Speed | 0.163 s per token, 6.1 tok/s over 98 steps (the runner does not stop at EOS) |

Why the 27th token differs: the device keeps activations in BF16 between operators (8 significant bits, the
official model's style), the reference in f32. That is about 1 % of noise per layer output and up to 0.2-0.7
logits at the end, enough to flip a close expert choice or a close token. It is not a logic difference: every
kernel is bit-exact against its own host anchor. An f32-activation build fixes it (section 8, done the same evening): 40 of 40 tokens equal.

Second speed round, before the six-card run (all bit-identical to the reference form on the card and the host,
gated per format as `lane_sum_*`): per-format block kernels for the five expert formats. The block scale is read
once per block, chunk words once per chunk, sign bits are computed (parity) instead of read from a table, and
each lane does one grid read. Kernel microbench, G elements/s, per-element form -> block form: IQ2_XXS 23 -> 302,
IQ3_XXS 53 -> 301, IQ1_S 129 -> 334, IQ2_XS 131 -> 293, IQ2_S 62 -> 266, Q5_K 49 -> 129. Layers 0-27: 103 -> 89 ms.

**Compiler hazard found by the gate:** for IQ2_S only, the block -> chunk loop nest gives wrong sums on lanes
1-31 on the B70 (icpx 2026.1), while the same source is right on the host and a flat chunk loop is right on the
card. IQ2_S uses the flat loop. Never ship a lane kernel without the on-card `lane_sum_*` gate.

Tried, slower: several rows per hardware thread (2 rows -9 %, 16 rows -57 %). Launch cost is not a lever: a tiny
kernel costs 1.6 us end to end.

## 8. f32 activations and the contract reference (17:15-17:40 EST)

The device executor is now built with **f32 activations by default** (`-DOWN41_ACT_BF16` keeps the BF16 build; its
decode trace is byte-identical to the build before the conversion). KV rows stay BF16. The reference got two
switches: `OWN_KV_BF16=1` (store KV rows as BF16 like the engine) and `OWN_CONTRACT=1` (sum in the device's order:
32 strided f32 lanes + the kernel's tree for every dot product, the same lane forms in double for the RMSNorm and
stream-mix statistics, f32 softmax and gates; build it with `-fp-model=precise -ffp-contract=off`).

| Device build | Reference | Tokens equal | Top-5 logits, largest difference | Block outputs (rel.) |
| --- | --- | --- | --- | --- |
| BF16 activations | f32, f32 KV | 26 of 40 (0.39-logit call lost) | 0.18-0.75 | 0.4-1.3 % |
| **f32 activations** | f32, BF16 KV | **40 of 40** | 0.005 for 8 steps, then 0.07-0.84 after one near-tied expert choice at step 9 | 5e-7 at layer 0, 4e-4 at layer 39 |
| **f32 activations** | contract order, BF16 KV | **14 of 14** (all that were run) | 0.007-0.021 | layer 0: embed, sublayer input, q, kv **bit-exact**; 2e-7 after the first softmax; 4e-4 at layer 39 |

Reading: against the contract reference every matmul chain is bit-exact; what remains is the last bit of `exp`
between host libm and the card (softmax, sigmoid, SiLU), which grows about 20 % per layer to 4e-4 at the output.
The plain reference's serial f32 sums were themselves 1e-4 off, enough to flip a sixth-of-six expert about once
in ten tokens. Speed is unchanged by f32 activations: 0.162 s per token, 6.2 tok/s (98 steps).

The on-card gate (`test_ops_v41_device.cpp`, 75 checks) now runs every weight format's lane kernel with both
activation types. It caught the compiler hazard a second time: **IQ2_XS with f32 activations** in the block ->
chunk nest is wrong on lanes 1-31 (right with BF16 activations, right on the host). IQ2_XS now uses the flat loop
like IQ2_S.

## 9. Third speed round: 6.2 -> 9.0 tok/s on six cards (17:40-18:10 EST)

| Change | s per token | Output |
| --- | --- | --- |
| start of round (f32 activations) | 0.162 | |
| router in three launches (score per expert, rank per expert, normalize) instead of one serial work-item; stream-mix statistics cut into 8 column segments (200 hardware threads instead of 25; anchor `ops41::hc_mix_lanes(seg=8)`, contract reference follows); engram rows prefetched (`madvise`) at step start | 0.147 | router bit-identical (gated); 100 tokens equal |
| mirrored state synced lazily: published rows and index lists stay on the host and a card is updated only when a layer on it reads them (was: copy to all six cards and wait on each queue, ~80 blocking round trips per token); top-512 of <= 512 rows is all rows, so no scoring below 512 compressed rows | **0.187 (slower)** | trace byte-identical |
| + **keep-warm**: after each layer, a 32-item kernel on every other card, then wait | **0.110** | trace byte-identical, 100 tokens equal |

**The finding that matters: an idle card clocks down, and a pipeline that visits six cards in turn leaves each one
idle five sixths of the time.** In the lazy build every kernel group, including untouched ones, ran a uniform 40 %
slower; the earlier design had been pinging all six cards constantly by accident (its broadcast waits). A deliberate
ping restores full clock for 0.6 ms per token. This changes no power setting (`OWN_KEEP_WARM=0` turns it off;
`=2` pings only the next card, 0.114 s). It does keep all six cards at full clock while decoding, so expect more
power draw during generation than the 0.19 s configuration. Extra queue waits between operators (`OWN_PACE`) and
waiting after host->card copies (`OWN_H2D_WAIT`) make no measurable difference once the cards are warm.

Six cards now: 0.111 s per token over 40 tokens, 0.113 s over 200 (8.8-9.0 tok/s); 40 of 40 tokens equal the
reference; load 165.3 GB in 20 s; no kernel fault line all day. Profile (ms per token): expert down 12.7, gate 11.9,
up 11.7, shared expert 11.3, attention core 10.9, output LoRA b 9.0 + a 6.7, query 7.5, stream mix 5.6, collapse +
norm 5.5, engram 4.8, head 4.3, router 3.0, keep-warm 0.6. Evidence: `profile-six-cards-round3-*.txt`,
`six-card-*-round3-*.log`, `device-gates-76.log`.

Long contexts are not measured yet: above 512 compressed rows the indexer scores on the card and selects on the
host (one blocking read per index layer), and the attention core always walks 640 slots.

## 10. Cards only: prompt in, answer out (18:20 EST)

`OWN_PROMPT=ids.txt own_run_v41 - N out.txt` reads the prompt on the cards, one decode step per prompt token from
an empty state, then generates and stops at the end-of-sentence token (`OWN_EOS`, default 1). No CPU reference
state is involved. The model is causal, so this equals a batched prompt pass; prompt reading runs at the decode
rate until a batched pass exists.

| Prompt | Prompt read | Answer | Text |
| --- | --- | --- | --- |
| "Say hello in one sentence." (36 tokens) | 3.95 s, 9.3 tok/s | 44 tokens, 9.2 tok/s, EOS | `...</think>Hello! It's nice to meet you, and I'm here to help with whatever you need.` |
| "Write a one-line Python function that reverses a string." (41 tokens) | 4.57 s, 9.1 tok/s | 88 tokens, 8.7 tok/s, EOS | reasoning equals llama.cpp's saved answer word for word for its first ~45 tokens, then `reverse_string = lambda s: s[::-1]` (llama.cpp's pack: the `def` form) |

Prompt 1: the first 40 generated tokens equal the CPU reference that read the prompt on the CPU, and two fresh
processes give identical tokens. Start-up with a warm kernel cache: 20 s load + 0.17 s for the first step.
Evidence: `data/dsv41-bringup-20261109/cards-only-*`.

## 11. Fourth speed round: 9.0 -> 28.0 tok/s, output byte-identical (18:30-19:45 EST)

Goal from the owner: 25 tok/s with no quality loss. Every step below was checked the same way: the 3-step
decode trace (`OWN_TRACE`, 70 MB of tagged tensors) is **byte-identical** (`cmp`) to the 9.0 tok/s build, and
the 40-token and 128-token greedy answers to prompt 1 are identical. Each new kernel is also gated on the card
against the kernel it replaces (bitwise, every output).

| Build | Change | s per token | tok/s |
| --- | --- | --- | --- |
| start | 9.0 tok/s build of section 9 | 0.111 | 9.0 |
| p1 | Q8_0 dense and IQ2_XXS expert weights stored **packed** on the card (same bytes, regrouped so a 32-lane sub-group reads them with block loads; scales gathered in one place) and new kernels for them | 0.092 | 10.9 |
| p2 | the other four expert formats packed (IQ2_S, IQ3_XXS, IQ2_XS, IQ1_S); expert kernels loop over rows with 128 work-groups, so each work-group fills its grid table once | 0.074 | 13.4 |
| p3 | Q6_K, Q5_K and F32 dense weights packed (attention projections, head, shared expert, engram, router) | 0.058 | 17.3 |
| p4 | small operators rewritten for latency: RMSNorm (block loads, lane sums in double, same tree), stream-mix dot products + Sinkhorn finish on one sub-group, sparse-attention score / softmax / output | 0.042 | 23.8 |
| p5 | engram gate (15x) and the final argmax (45x, two passes; the answer is independent of scan order) | 0.038 | 26.05 |
| **p6** | window append on 512 work-items instead of one (42 -> 2 us per layer) fused with building the attention's index list (two queue copies gone); router score + rank + normalize in one work-group (33 -> 22 us per layer); compressor pool lane-parallel (316 -> 37 us) | **0.036** | **28.02** |
| p7 (20:00) | expert kernels address their grid table in bytes (one shift per weight fewer); IQ2_XXS sign words expanded by the packer to 8 bits per group (parity precomputed) and its 4-bit scales moved to their own array, per-chunk scales built lane-parallel; RMSNorm on 2-4 sub-groups | 0.034 | 28.99 |
| p8 (20:05) | four fused small kernels: stream post-mix (+ the pre-mix copy, no stream copy), SwiGLU + router weight, output conversion + inverse rope, stream pre-mix + RMSNorm. Byte-identical but **no faster** (28.90): the fused pre-mix + RMSNorm took 22.1 us in the real step against 11.4 for the two kernels it replaced (19 vs 23 us in the gate). That one is switched off in p9; the other three stay | 0.035 | 28.90 |
| **p9** (20:20) | sparse-attention output reads each key row with a sub-group block read at a uniform address (the per-lane 64-bit address arithmetic per index was the cost, not load latency: a software-pipelined form was no faster); 35 -> 20 us per layer | **0.033** | **30.14** |

| **p10** (20:45) | the router (one work-group of serial work) runs in the same launch as the shared expert's gate and up rows (memory-bound), 52 -> 28 us in the gate; the routed SwiGLU and the shared SwiGLU in one launch. Router + shared expert 4.95 -> 3.77 ms per token | **0.032** | **31.24** |

p7-p10: trace, 40-token and 128-token answers byte-identical to the 9.0 tok/s build. IQ3_XXS with expanded signs was
7 % slower (98 vs 91 us) and stays on its original layout. Gate timings for the sparse-attention output at 640
slots (`test_small_v41_device.cpp`, card e3): SparseOutJ2 39.3 us, pipelined loads 40.1, address formed once per
round 29.3, block reads 25.1 (8 per batch) / 22.8 (16 per batch, used). Closed: the shared expert's dense rows run
*inside* the routed expert launches (rows interleaved, `DenseRows` extra rows; bitwise equal) save nothing: the
routed kernel slows by about the dense rows' own time (-15 to +12 us across formats,
`kernel-gates-round5-fused.log`), so the expert kernels have no spare issue slots for memory-bound rows.

How the kernels stay exact: each output is still summed by 32 lanes in the old order (lane l adds elements l,
l+32, l+64, ... one at a time, multiply then add, no fused multiply-add; build flags `-fp-model=precise
-ffp-contract=off`) and reduced by the same tree. Only *where the bytes sit* and *how many loads fetch them*
changed. Per-block scales are computed once per row in parallel across lanes and broadcast from a fixed lane.

Kernel gates (card e3, all **0 differing outputs**; `data/dsv41-bringup-20261109/kernel-gates-round4-*.log`):

| Kernel | old | new |
| --- | --- | --- |
| expert IQ2_XXS 6 x 2304 x 5120 | 281 us | 83 us |
| expert IQ2_S 6 x 2304 x 5120 / 6 x 5120 x 2304 | 369 / 373 us | 123 / 106 us |
| expert IQ3_XXS, IQ2_XS, IQ1_S | 243, 375, 252 us | 99, 99, 104 us |
| Q8_0 dense (attention query 32768 x 1280) | 190 us, 235 GB/s | 76 us, 588 GB/s |
| Q6_K head 129280 x 5120 | 3670 us | 935 us (581 GB/s) |
| Q5_K engram projections | 164 / 104 us | 20 / 17 us |
| RMSNorm 5120, stream-mix finish | 61, 54 us | 15, 14 us |
| sparse attention, 640 slots (score + softmax + output) | 70 + 271 + 110 us | 9 + 11 + 39 us |
| engram gate, argmax | 1432, 458 us | 97, 11 us |
| window append + index list, router, compressor pool | 145, 65, 305 us | 2.2, 14.8, 32 us |

**A fault on the way, our own bug (saved, fixed, probed):** the first packed IQ2_XXS kernel read whole 32-word
blocks past the end of a 9-block row (144 quant words in a 152-word row); on the last row of the bank that ran
off the allocation and card e3 page-faulted twice in the microbenchmark (`data/fault-20261109-rq-bench/`, fault
address = end of the packed bank). The same overrun was latent in p1. Fix: `row_words<NW>` reads per lane past
the last full block. Health probe passed both times; no fault line since.

Facts measured on the B70 that shaped the kernels: a dependent double add costs ~26 ns, a float add ~8.6 ns, a
precise float divide ~81 ns; a plain per-lane load in a lane loop is issued one at a time (~290 ns each), so
small kernels need sub-group block loads; holding 160 floats per lane spills registers; an empty kernel costs
1.5-2 us; a single launch's time drifts with the card clock, so kernels are timed back to back.

GPU time per token at p6 (OWN_GPROF=2, 37.6 ms with profiling barriers; `round4-p6-kernel-profile.log`): kernels
34.3 ms in 1,514 launches, gaps and copies 3.3 ms. Expert kernels 12.4 ms (IQ2_S 5.2, IQ2_XXS 2.8, IQ1_S 2.1,
IQ3_XXS 1.4, IQ2_XS 0.6, one unpacked Q2_K 0.36), dense Q8_0 8.7, Q6_K 4.1, sparse attention 2.2, RMSNorm 1.6,
stream mix 1.6, router 1.5. The dense projections run at 550-600 GB/s (the card's memory speed). The expert
kernels at 130-270 GB/s are limited by instructions per weight, not memory: the machine code of the IQ2_XXS
kernel has about 10 ALU instructions per weight (4 of them only for the sign bit), IQ2_S about 14 (IGC dump:
`IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=... NEO_CACHE_PERSISTENT=0`).

Switches: `OWN_PACKED=0` (raw rows, old kernels), `OWN_SMALL=0` (old small operators), `OWN_GPROF=1` (GPU time
per operator group, profiling barriers), `OWN_GPROF=2` (also time per kernel type). Upload is 33 s now (was 20 s):
the host packs rows while uploading.

## 12. Every layer on all six cards: 31.2 -> 47-52 tok/s (20:45-22:30 EST)

Until p10 each card held whole layers and the six cards took turns (one busy, five idle). `OWN_TP=6` splits
**every layer across all six cards** (commit a0d94e2c4, plus the follow-ups in section 13's commit):

- Row slices, so every output element is still computed whole on one card by the same kernel (no partial sums
  added across cards, so nothing changes bitwise): query up-projection by heads following the eight output
  groups (cards get 1,1,2,1,1,2 groups), output-a by group, output-b / expert down / shared down by rows of the
  hidden size (16-aligned), expert and shared gate/up by rows of the 2304 intermediate (384 each), head by
  vocabulary. Everything else (norms, stream mixing, router, the attention bookkeeping) runs replicated.
- Four all-gathers per layer (output-a, output-b, the SwiGLU outputs as 7 slots, the FFN output), done by one
  kernel (`XchgP`) that writes this card's slice straight into the five peers' memory (Level Zero IPC handles
  opened in each card's own context), then a system-scope release fence and a sequence-number flag per peer;
  the reader spins on its own memory. Buffers are never reused before every reader has passed them (reuse
  distance >= 2 exchanges), slices are 64-byte aligned. A timed-out wait (~0.9 s) poisons the card's later
  waits and reports the peer, so a fault fails one step instead of hanging.
- One host thread per card submits that card's whole step; trace runs (`OWN_TRACE`) submit phase by phase from
  one thread so the record order equals the one-card-per-layer build. The index top-k needs the host only past
  512 tokens; below that a kernel fills the list (`CidxFill`). Publishing the compressed rows runs on every card;
  the engram rows for the next step upload while the current step runs.
- `sync_rows` no longer drains the card's queue when it has nothing to copy (the drain stopped the card's
  pipeline once per layer: 47 -> ~51 tok/s).

Gate (each change): 3-step trace `cmp`-identical to the 9.0 tok/s build for `OWN_TP=6` and for the old layout,
40-token and 128-token answers identical. 47.42 tok/s at a0d94e2c4 (`round6-tp6-*`); 49.9-51.5 with the drain
fix. The profile at that point (card 0, `OWN_GPROF=2`): kernels 15.8 ms of a 25 ms profiled step, 1,473 launches
per step; the exchanges 3.7 ms (160 per step, ~15 us each including the wait for the slowest card). Head-count
balancing between cards is closed: the sparse-attention kernels are latency-bound, imbalance ~0.5 ms.

## 13. The driver's launch lock: 50 -> 60 tok/s (2026-11-09 22:30-23:15 EST)

With six submitting threads the host, not the cards, set the pace. `perf` on a running decode: 62 % of host
time inside `ur_command_list_manager::appendKernelLaunchLocked`, much of it a `pthread_rwlock_wrlock` futex in
`libze_intel_gpu` (the same calls take ~2.9 us per launch from one thread and 6-13 us with six). Two driver
switches that sound right did not help (`MakeIndirectAllocationsResidentAsPack=1` 45.2, `DetectIndirectAccessInKernel=1`
46.1, control 49.9 tok/s).

Cause, pinned with a bench (`engine/tools/l0_launch_lock_bench.cpp`): **a kernel the compiler marks as
"indirect access" makes every launch re-register all allocations under one lock shared by every thread of the
process.** Six threads launching such a kernel cost 10-11 us per round of six launches, plain kernels 2.5 us.
The marks (`is_ptr` on a by-value argument, or `indirect_stateless_count > 0` in the kernel's zeinfo) come from
a pointer inside a by-value struct (the exchange kernel's peer table), a pointer loaded from memory, a
program-scope table (the expert grid tables), and even a plain data-dependent address like `p[ix[i]]` (every
sparse-attention and routed-expert kernel). 47 of the engine's 230 kernels carry a mark, 22 more only reference
a program-scope table (`round7-indirect-kernel-census.txt`, from `-fsycl-dump-device-code` + `ocloc compile
-device bmg`); in the six-card step that is roughly 390 of the 1,473 launches. Allocation count does not matter (1,000 extra allocations: no change).

Fix: the driver switch `DisableIndirectAccess=1` (with `NEOReadDebugKeys=1`), set by `own_run_v41` before the
cards start (`OWN_INDIRECT_ACCESS=1` keeps the driver default). Without the bookkeeping, an allocation that
kernels only reach indirectly would never be made resident, so (a) the exchange kernel takes the six peer
arenas as direct pointer arguments (it was the only kernel that reached memory no other kernel names), and (b)
every allocation the engine owns or opens is passed once to a one-item kernel as a direct argument when it is
made (`Backend41::touch`: `dalloc`, the error words, the opened peer arenas). The bench: 2.4 us per round with
the switch.

| Run (128 tokens, prompt 1) | tok/s | answer |
| --- | --- | --- |
| six cards, switch on (two runs) | **60.10, 59.96** | identical |
| six cards, driver default (same build) | 43.94 (earlier runs 47-52) | identical |

Trace gate: `OWN_TP=6` and the one-card-per-layer layout both `cmp`-identical, 40-token answers identical
(`round7-launch-lock-gate-summary.txt`); no fault line in the kernel log. Prompt reading on the cards (still one
token per step): 36 tokens in 0.63 s (60 tok/s).

## 14. Stream mix inside other launches, router rows halved: 60 -> 66 tok/s (23:15-23:45 EST)

Profile after section 13 (card 0, `round7-tp6-kernel-profile-card0.log`; card 2 with two output groups in
`-card2.log`): 18.3 ms profiled step, kernels 15.2 ms in 1,483 launches, 3.0 ms idle between kernels; the
exchanges 1.8 ms (11.3 us each on card 0, 9.4 us on card 2: card 2 has ~0.6 ms more query/output-a work and the
others wait for it); stream mixing and pre-norms 2.4 ms, repeated on every card.

- **Stream mix riding in later launches** (`OWN_HC_RIDE`, default on). A sublayer's pre-norm uses the *previous*
  sublayer's pre-mix (the attention's `cur_pre`, the FFN's `pre_a`), so the mix this sublayer computes is first
  read at its `hc_post`. Its 200 dot partials now run as extra sub-groups in the query-a launch (attention) or
  the router launch (FFN), and the one-sub-group Sinkhorn finish in the query-b launch / the router-select +
  shared-rows launch (`HcDotsRows`, `HcFinishRows`, `RowsP`, `gemv_ex`; same per-sub-group code as
  `HcMixDotsP` / `HcMixFinishSG`). 160 launches fewer per step. 60.19 -> 64.66 / 64.55 tok/s.
- **Router rows halved** (`OWN_ROUTER16`, default on). `ffn_gate_inp` is F32 in the GGUF, but every one of its
  values has zero low 16 bits (checked over all 40 layers; the other F32 matrices, e.g. `hc_*_fn`, do not).
  Stored as the upper halves and widened on the card (`GemvH16P`), the products are bit-identical with half
  the bytes; the packer refuses the upload if any value is not exact. 64.60 -> 65.90 / 66.03 tok/s.
- `GemvQ6KP` and `GemvF32P` got the one-row form (`row()`) the other packed kernels have, body unchanged.

Gate (both): 3-step trace `cmp`-identical for `OWN_TP=6` and the one-card-per-layer layout, 40- and 128-token
answers identical, no fault line (`round8-*-gate-summary.txt`).

Looked at and set aside: the engram gate (118 us twice per step) sums three 5,120-long chains serially in
double, element order (part of the arithmetic), so its time is the chain; splitting the engram matrix (224 us,
repeated on all cards) across cards would save ~0.3 ms per step, not done yet.

## 15. Launch diet, stage 1: 66.3 -> 67.0-67.4 tok/s (2026-11-10 00:00-00:40 EST)

`OWN_DIET` (default on) merges neighbouring launches when the stream mix rides (section 14); every merged piece
runs the same per-sub-group code as its old kernel:

- The FFN's `hc_post` and the next sublayer's stream collapse (`HcPreA`) are one launch (`HcPostPreP`): it
  writes the new streams, then collapses them with the pre-mix it is given. After the FFN this also prepares the
  next layer's attention input (`x_ready`), so the next layer starts at its norm (not before layers 1 and 14,
  which add their engram row first, and not at the last layer without the head).
- Attention input: query-a and kv rows in one launch with the mix dots (`gemv_pair_ex`), both norms in one
  launch (`NormRows`), the kv rotary step and the mix finish ride in the query-b launch (`RopeRows`,
  `HcFinishRows`), then the query rotary step. Five launches fewer per layer.

Gate (`round9-diet1-gate-summary.txt`): 3-step trace `cmp`-identical for `OWN_TP=6` and the one-card-per-layer
layout, 40- and 128-token answers identical, no fault line. 67.02 / 67.37 tok/s against 66.31 with `OWN_DIET=0`
in the same session (`round9-tp6-speed-128.log`).

## Reproduce

```bash
cd experiments/own-xpu-runtime/engine
ICPX=/opt/intel/oneapi/compiler/latest/bin/icpx
$ICPX -O3 -fiopenmp -std=c++20 -DOWN_RT_HOST_ONLY -I src -I planning/dsv41-fixtures \
  -o cpu_run_v41 planning/dsv41-fixtures/cpu_run_v41.cpp
$ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -I planning/dsv41-fixtures -I src \
  planning/dsv41-fixtures/own_run_v41.cpp -o own_run_v41 -lze_loader
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
# reference: prompt ids -> 40 tokens, state dump, 3-step trace (KV rows BF16 like the engine;
# add OWN_CONTRACT=1 and build with -fp-model=precise -ffp-contract=off for the device's summation order)
OWN_KV_BF16=1 OWN_TRACE=cpu.trc OWN_TRACE_STEPS=3 OMP_NUM_THREADS=16 ./cpu_run_v41 ids.txt 40 ref_ids.txt 4096 \
  <shard 6> /dev/null state.bin
# cards only: prompt ids in, generated ids out (stops at end of sentence)
OWN_PROMPT=ids.txt ./own_run_v41 - 200 out_ids.txt 4096
# every layer split across the six cards (fastest; OWN_GPROF=2 OWN_GPROF_CARD=c profiles card c)
OWN_TP=6 OWN_PROMPT=ids.txt ./own_run_v41 - 200 out_ids.txt 4096
# from the reference's state, with a trace for the gate (cards must be empty; the runner refuses otherwise)
OWN_DEBUG=1 OWN_TRACE=dev.trc OWN_TRACE_STEPS=3 ./own_run_v41 state.bin 40 dev_ids.txt 4096
python3 tools/dsv41_trace_diff.py cpu.trc dev.trc
# a subset of cards: OWN_LAYERS=0:28 OWN_HEAD=0 OWN_DEVS=2,3,4,5 OWN_FORCED=ref_ids.txt
#                    OWN_LAYERS=28:40 OWN_DEVS=2,3 OWN_INJECT=cpu.trc OWN_FORCED=ref_ids.txt
```

Long GPU runs go in their own unit (`systemd-run --user`). The Gemma units were stopped and disabled by the
owner on 2026-11-09; if they are ever enabled again they take two cards at boot and the runner will refuse.

## Open

1. A server front end (tokenizer + chat template in the engine; today token ids come from a helper script).
2. Speed, next levers: the weight matmuls are now 75 % of the time at 200-330 G elements/s (flat-loop forms for
   Q6_K/Q5_K, which carry the deeper layers, the head and the engram projections); the attention core at short
   context (compact the live slots); top-512 selection on the card for long contexts.
3. A batched prompt pass on the cards (today the cards read the prompt one token per step, 60 tok/s with
   `OWN_TP=6`).
4. `compress_ratios`, window and top-k constants are hardcoded in three places; they belong in the profile.
5. A float-exact llama.cpp comparison to remove the remaining noise from section 4; report the nested-loop
   miscompile (IQ2_S, IQ2_XS/f32) upstream with the standalone reproducer shape from the gate.
