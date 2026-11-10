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

## 12. Every layer on all six cards: 31.2 -> 47-52 tok/s (20:15-21:00 EST)

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

## 13. The driver's launch lock: 50 -> 60 tok/s (2026-11-09 21:00-21:15 EST)

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

## 14. Stream mix inside other launches, router rows halved: 60 -> 66 tok/s (21:15-21:30 EST)

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

## 15. Launch diet, stage 1: 66.3 -> 67.0-67.4 tok/s (2026-11-09 21:30-21:40 EST)

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

Section headers 12-15 were first written with times about two hours late; corrected from the commit times.

## 16. Engram projection split across the cards: 67.0 -> 68.3-68.5 tok/s (21:40-21:50 EST)

Profile at section 15 (`round9-tp6-kernel-profile-card{0,2,3}.log`): 1,125 launches, kernels 13.7-14.0 ms of a
16.1-16.5 ms profiled step. The two-output-group cards (2 and 5) spend ~0.5 ms more per step on query-b and
output-a, but the others' exchanges are only ~1 us longer on average (~0.15 ms per step): balancing it would need
one more exchange per layer, so it stays.

- **`OWN_ENG_SPLIT`** (default on): `engram_kv` (25,600 x 6,144 Q6_K, 129 MB per engram layer, 223 us on every
  card) reads only the hashed rows of the current token, so it does not wait for the layers before it. Each card
  now holds and computes 1/6 of its rows for both engram layers at the start of the step and pushes them to the
  peers with a push-only exchange (`XchgP` mode 1, no wait). Layer 0's exchanges come later in every peer's queue,
  so their waits already cover the engram rows; when layer 1 is the first layer, a wait-only exchange (mode 2)
  runs before the gate. Rows are the same per-row kernel code, so the values are identical. Also saves ~215 MB
  of card memory per card.

Gate (`round10-engsplit-gate-summary.txt`): 3-step trace `cmp`-identical (`OWN_TP=6`), 40- and 128-token answers
identical, no fault line; 68.50 / 68.33 tok/s against 66.95 with `OWN_ENG_SPLIT=0` in the same session.

## 17. Expert gate + up in one launch, softmax chain: 68.3 -> 71.2-71.7 tok/s (21:50-22:10 EST)

- **`OWN_EXP_PAIR`** (default on). The routed kernels run as 128 persistent work-groups (2,048 sub-groups, what
  a card holds at once at 128 registers). With six-way splitting a card's gate launch has 6 x 384 = 2,304 rows:
  one full round and a second round of 256 rows that costs nearly a full round (the kernels are ALU-bound, about
  10.8 us per round for IQ2_XXS). Gate and up now run in one launch (`w2`/`out2` in the routed kernels: rows
  6 x rows .. 12 x rows read the second matrix; same per-row code), 4,608 rows = 2.25 rounds instead of 2 x 2.
  68.08 -> 71.14 / 71.11 tok/s (`round11-exppair-gate-summary.txt`).
- **Softmax chain** (`SparseSoftmaxP`): the element-order sum skipped unused slots with a select inside the
  chain; they now add +0, which leaves a sum of exp terms (>= +0) unchanged, so the chain is one add per element.
  Bench 22.96 -> 12.25 us (differ 0 of 10,240); in the step 10.5 -> 5.3 us per layer.
- Profile (card 0, `round11-tp6-kernel-profile-card0.log`): kernels 12.8 ms of a 15.0 ms profiled step, 1,086
  launches; exchanges 2.0 ms, experts 3.2 ms, router + shared 1.5 ms, norms 0.8 ms, attention 1.2 ms.

Tried and left off (switches kept, results in `round11-*`):
- `OWN_DOWN_EX=1`: the shared expert's down rows as extra rows of the expert down launch (6 x 853 + 853 rows =
  2.9 rounds). 70.45 / 69.74 against 70.72: no gain.
- `OWN_FIN_MOVE=1`: the stream-mix finishes ride in output-b's and the expert pair's launches instead of
  query-b's and the router-select launch. Byte-identical, but 70.23 / 69.49 against 71.48.
- `OWN_PF=1`: extra work-groups in the attention launches prefetch output-a/b rows into the card's 24 MiB cache.
  Output-b 15.95 -> 11.93 us and output-a 10.11 -> 7.29 us, but the score and output launches grow by 6.7 and
  9.6 us because a launch ends only when its prefetch work-groups do: 68.83 / 68.35 against 71.47 / 71.34.
  Bench (`bench_l2`, card 0): a 5.6 MB Q8_0 GEMV takes 12.9 us from memory, 9.8 us from the cache after a
  separate prefetch, 7.0 us right after itself; pulling 5.6 MB into the cache takes ~10 us.

Gate (defaults, `round11-defaults-gate-summary.txt`): 3-step trace `cmp`-identical for `OWN_TP=6` and the
one-card-per-layer layout, 40- and 128-token answers identical, no fault line; 71.68 / 71.23 tok/s.

## 18. Mix dots inside the norm launch, inverse rope in the output store: 71.5 -> 73.7-73.9 tok/s (22:10-22:25 EST)

- **`OWN_NORM_DOTS`** (default on). The 5,120-wide pre-norm is a serial double chain on four sub-groups (~10 us)
  with the rest of the card idle. The stream mix's 200 dot partials only read the streams (final before the
  norm), so they now run as extra rows of the norm's launch (`norm_ex`: `RowsP<RowsPair<NormRows<5120,4>,
  HcDotsRows>>`) instead of the query-a or router launch: the FFN norm always, the attention norm when the
  previous FFN's `hc_post` already collapsed the streams (`x_ready`). 71.66 / 71.48 -> 72.82 / 73.02 tok/s
  (`round12-normdots-gate-summary.txt`).
- **`OWN_ROPE_OUT`** (default on). `SparseOutJB` writes the head row a second time into the output-a input with
  the last 64 dims rotated back (lane = pair index of the last span; `ToActRopeA`'s expressions), so the
  separate inverse-rope launch is gone. 72.55 / 73.31 -> 73.93 / 73.67 tok/s (`round12-ropeout-gate-summary.txt`).
- **Kernels built at start-up for every card** (`get_kernel_bundle<executable>`, one card after the other). The
  first threaded run of a new binary timed out an exchange on the first token (no card fault): one card was still
  compiling a kernel at its first launch while a peer waited >0.9 s for its flag. Earlier gates began with a
  single-thread trace run that warmed the driver's compiler cache. Now 12.6 s once per new binary, 0.2 s after.

Tried and left off: **`OWN_XTAIL=1`**, the exchange run by the last work-group of its producer's launch
(release + counter per work-group, `xchg_tail`) to drop one launch per exchange: 66.6 / 67.1 against 73.2
(`round12-xtail-summary.txt`; its first form also ran the exchange before the producer with the switch off,
which the 128-token check caught).

Gate (defaults): 3-step trace `cmp`-identical for `OWN_TP=6` and the one-card-per-layer layout, 40- and
128-token answers identical, no fault line.

## 19. Long context: index selection on the cards, 55.4-55.7 -> 67.9 tok/s at 3K and 10K tokens (22:30-23:05 EST)

Prompts: 3,323 and 10,621 tokens (a chat-templated request over a long document, `tools/mk_prompt_ids.py`),
64 answer tokens each; reference answers from the one-card host-index path (`round13-longctx-host-index-summary.txt`:
decode 55.73 / 55.42 tok/s, prompt reading 58.8 / 57.9 tok/s). Above 512 compressed rows every index layer used
to score on the card, copy the scores to the host, select the top 512 there and copy the list back to every card.

- **`OWN_DEV_INDEX`** (default on): the selection runs on the card, exactly. `TopKSelP` (kernels): one work-group
  of 1,024, a radix select over four 8-bit passes with per-sub-group histograms in shared memory, then an in-order
  compaction, so ties go to the lower row and the list comes out ascending (+128 for the window), the host's
  order. The layer-20 candidate mask (block 8, top 2,048, newest block always in) is the same kernel with
  `BLOCK=true`. `OWN_DEV_INDEX_CHECK=1` compares every list with the host selection: 475,136 lists, 0 mismatches
  at 10K (`round13-devindex-summary.txt`). Decode 59.8 / 57.5 tok/s.
- **`OWN_SCORE_B`** (default on): the indexer score as one row per work-group with the query and weights in shared
  memory and each key row read once, same per-row sums in the same order as `IndexerScoreA` (heads in order, 128
  products in order). 14-27x faster alone and bitwise identical at 513 to 131,072 rows
  (`round13-indexer-score-bench.txt`, `tools/bench/test_index_score.cpp`). Decode 67.1 / 67.7 tok/s.
- **Head skipped for prompt tokens** that are not the last (`skip_head`): prompt reading 58.8 / 57.9 -> 69.6 /
  69.9 tok/s.

Gate (all on as defaults, `round13-defaults-gate-summary.txt`): 3-step trace identical for `OWN_TP=6` and the
one-card-per-layer layout, 40- and 128-token answers identical, 3K and 10K answers identical to the reference,
decode 67.86 / 67.85 tok/s. Short-context speed unchanged: old/new alternating 73.51 / 73.18 / 72.98 / 72.91
(`round13-short-old-new-summary.txt`). Card 0 profile at 3K: `round13-tp6-kernel-profile-p3k-card0.txt`
(exchanges 11.5 %, the norm + mix-dots launch 7 %, attention output 5.6 %).

Next: a step that runs up to 16 tokens at once with each token's result bit-identical to the one-token step, for
prompt reading and then for checking DSpark draft guesses
(`2026-11-09-dsv41-multitoken-and-dspark-plan.md`).

## 20. Reading the prompt 16 tokens per step: 69.6-69.9 -> 90.0-91.5 tok/s, answers identical (2026-11-09 23:10-23:50 EST)

`backend/backend_sycl_v41_mt.inc` (included in `Backend41`), runner `OWN_PROMPT_BLOCK=m` (m <= `MTX` = 16):
one step runs m prompt tokens, and every token's results are bit-identical to the one-token step, so the
state after the prompt is the same bytes and the answer cannot change.

- **Weight rows**: `rowm<MT>` in every dense row kernel (`GemvQ8P`, `GemvQ6KP`, `GemvQ5KP`, `GemvH16P`,
  `GemvF32P`, `GemvT`) decodes a weight block once and runs each token's own accumulator through the
  one-token op sequence and tree (`DenseRowsM`, `DenseM`, `GemvTM`). `tools/bench/test_rows_mt.cpp`:
  104 checks bitwise on card 0 (MT 1/4/6/8/16, mt = MT and MT - 1; `round14-rows-mt-test-card0.txt`).
- **Small ops**: per-token buffers at fixed strides; `TokRows<R>` runs the one-token row op on token t's
  pointers, so norms, stream-mix dots/finishes, rope, router, swiglu and combine for all tokens go in one
  launch each (`OWN_MT_SMALL=0` keeps one launch per token, the first form).
- **Attention**: ring of 128 + 16 rows per layer; the block's key rows go to rows 128 + t and
  `RingCommitM` moves them to their ring rows after every token has read them. Index lists shift block
  rows accordingly. Ratio-2 compressor: `StatePackM` stacks the carried even state and each token's
  state, odd tokens pool rows (t, t + 1) (`CompressPoolPM`), publish/index per token with each token's
  own row count (`tpm_publish`, `tpm_index`, `IndexerScoreBM`, `TopKSelM`).
- **Routed experts**: 6m slots through the existing slot kernels (`nsl`, `xtok`).
- **Exchanges**: m rows per exchange (section 21 replaced the stores by loads).

Gate (every build): 3-step decode trace identical after a prompt read in blocks of 16, 7 and 5
(`OWN_TP_THREADS=1` keeps the worker threads and runs traced steps serially), 40- and 128-token answers
identical, the 3K and 10K answers identical to the one-token reading, a block of 13 on 3K identical.

| build | 3K prompt tok/s | 10K prompt tok/s |
| --- | --- | --- |
| one token per step (section 19) | 69.6 | 69.9 |
| blocks of 16, one launch per token for small ops | 63.1 | - |
| + merged small launches | 76.6 | 75.8 |
| + block attention | 86.1 | 85.1 |
| + block index, many-group exchange push, `TokRows` mix dots | 87.8 | 89.2 |
| + block publish | 90.0 | 91.5 |

**Checking guesses** (`decode_verify_tp(toks, m, next)`): one block step with the head for every token
(per-token argmax over the cards' candidates); `commit_block(n)` keeps the first n tokens: row counts from
the per-token `mlen`, the ratio-2 carried state restored from the block's state row n when the last kept
position is even, position reset. Runner test `OWN_VERIFY_TEST=k OWN_VERIFY_BAD=pct`: blocks [token, k
guesses] from the plain run's answer with pct % of the guesses replaced; the kept text must equal the plain
run. The first build failed every test with a wrong guess: `RingCommitM` moved every block token's key row
into the ring, and a dropped token's row overwrote the row of position - 128, which the next tokens' windows
still read. Now the rows stay in the block area and `commit_block` moves the kept tokens' rows only.

## 21. The card-to-card exchange by loads; token groups; shared expert rows (2026-11-09 23:50 - 2026-11-10 00:40 EST)

**Peer stores are slow, peer loads are fast on this host.** `tools/bench/xchg_bw_bench.cpp`
(`round15-xchg-bw-bench.txt`): a kernel storing into another card's memory moves ~1 GB/s per card whatever the
shape (push from many work-groups, a work-group per destination, one fence), the copy engine 7-25 GB/s with all six
cards busy, kernel loads from the peers 23-25 GB/s. The block step's exchanges were about half its time.

- **`XchgPull`** (kernels; `OWN_XPULL`, default on, for slices of at least `OWN_XPULL_MIN` = 8,192 bytes): work-group 0
  publishes (system-scope release fence, then the sequence number into every peer's flag word); every work-group waits
  for the peers' flags, then copies the peers' rows into its own arena with vector loads. A region is rewritten only
  after a later exchange, which a peer raises only after its copy, so no copy can read a newer row.
  `tools/bench/xchg_pull_test.cpp` (`round15-xchg-pull-test.txt`): 0 wrong values in 2,000 iterations of every
  shape with changing data; a block of 16's activation exchange 773 -> 40 us, a block of 6's 237 -> 20 us; the
  one-token h exchange (3,456 bytes) stays a push (8.9 vs 12.0 us).
- Fault while writing the bench (23:58:37, all six cards, `fault-20261109-2358-xchg-bench/`): the bench passed peer
  pointers inside a by-value struct, which this driver mode (`DisableIndirectAccess=1`) does not make resident. Peer
  pointers go to kernels as direct arguments only (the engine already did). Evidence saved, health probe passed, no
  later faults.

Gate (`round15-pull-gate-summary.txt`): traces identical after blocks of 16, 7 and 5; 40- and 128-token answers
identical; 3K and 10K answers identical. Prompt reading 94.7 -> **179.2 tok/s at 3K, 174.4 at 10K**; decode
74.6-74.8 -> **75.7-76.7 tok/s** (two runs each); verify tests: all guesses kept, 30 %, 100 % and 50 % wrong, blocks
of 4, 6 and 16, on prompt 1, 3K and 10K: every kept text the same as the plain run.

Profile of a checked block of 6 (all kept, card 2, `round15-verify6-cycle-profile-card2.txt`): 44.3 ms of kernels
per cycle; the dense weight rows ~22 ms, routed experts ~11 ms, exchanges 4 ms. A 384-row slice at 6 tokens was 384
sub-groups, one row each, so most of the card sat idle.

- **Token groups over sub-groups** (`DenseRowsG`, `OWN_MT_TG=1/2/4`, `OWN_MT_TG_MAX`): position p runs row p / ng's
  token group p % ng through the kernel's `rowg<G>` (the group body `rowm` ran one after another), so each token's
  operations are unchanged.
- **Shared expert rows** (`ExpertGroupM` + `RoutedU`, `OWN_MT_EU=6`; written by a subagent, checked here): the slots
  of a block that picked the same expert form a group (at most 6); a sub-group decodes each block of an expert row
  once and runs every slot of the group through its own accumulator in the slot kernels' order.
  `tools/bench/test_routed_u.cpp` on card 0: 41 of 41 bitwise checks (5 formats, both shapes, splitting groups);
  gate+up 1.23-1.39x at 6 tokens, 1.44-2.19x at 16 (`round15-routed-u-test-card0.txt`).

Gate (`round15-tg-eu-gate-summary.txt`): traces identical after blocks of 16 (TG 2 + EU), 5 (TG 1 + EU) and 7
(TG 4); every verify run the same as the plain run; 3K answers identical.

| checked block of 6, all kept (prompt 1, 128 tokens) | tok/s | ms per cycle |
| --- | --- | --- |
| section 20 build | 75.9 | ~76 |
| exchange by loads | 120.9-122.9 | 47 |
| + token groups of 2 | 162.0 | 35 |
| + shared expert rows | **176.8** | **32.7** |

| 3K prompt, blocks of 16 | tok/s |
| --- | --- |
| exchange by loads | 176.6-179.2 |
| + shared expert rows | 202.6 |
| + token groups of 4 | **250.7** |
| (token groups of 2 instead) | 242.4 |

## 22. The official DSpark draft on the cards: 3K answers 68.7 -> 86.8 tok/s, text identical (2026-11-10 00:10-01:35 EST)

The DSpark draft that DeepSeek publishes with V4.1 Flash (Unsloth's Q8_0 GGUF of it,
`dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf`) now runs on the six cards next to the target
(`backend/backend_sycl_v41_draft.inc`, kernels `kernels/sycl_v41_draft.hpp`; semantics from llama.cpp's
`src/models/dflash.cpp` `graph_dsv41` and `build_dspark_markov_head`, read for semantics only, credited in
`2026-11-09-dsv41-multitoken-and-dspark-plan.md`). Runner: `OWN_DSPARK=<gguf> OWN_SPEC=k` (k = 1..5 guesses per
round). Placement: `profiles/dspark-q8/placement.tsv` (`tools/mk_dspark_placement.py`); the draft's tensors split
across the cards by the target's rules (`tp_rows`), `dsp.fc` replicated.

- **Draft step** (`draft_tp`, `dr_card_step`): the block [anchor, MASK x 4] at positions pos .. pos + 4 through 3
  stages of the target's layer shape (non-causal attention over the stage's 128 window rows plus the 5 block rows;
  single-pass stream mixing; 128 MXFP4 experts, top 3, `RoutedMXFP4`), then output norm, the target's output rows
  and the Markov chain (row i's logits + `markov_w2 . markov_w1[prev]`, prev = the anchor or row i - 1's pick; each
  row's pick crosses the cards through a 24-float exchange: `DraftBest` -> exchange -> `DraftPick`). 3.3 ms.
- **Features**: the mean of the 4 streams at the inputs of target layers 37, 38, 39 (`StreamMeanM`, captured in
  `tpm_layer`), through `fc`, `enc.output_norm`, each stage's `attn_kv`, `kv_a_norm` and rope into the stage's window
  ring. Prompt blocks inject directly; a checked block's rows are staged in the ring's block area and only the kept
  ones are moved (as the target's own window rows, section 20).
- **Checking** reuses section 20's `decode_verify_tp` (each token bit-identical to the one-token step) and
  `commit_block`; the kept text is the target's greedy text by construction. Every run in this section: **SAME AS
  the plain run**.

Rounds of speed work on the checking step (all pure speed changes; traces identical after blocks of 16, 7, 6 and 5;
the 40- and 128-token answers identical):

1. `commit_block` did its card work (ratio-2 state, 40 window-row moves, the draft's rows) from the main thread one
   card at a time: now it records the commit and each card applies it at the start of its next step
   (`commit_pending`), all cards at once; the draft rows are staged by the checking step itself. Check 41.7 -> 33.7
   ms per round at k = 5.
2. The unpacked rows (BF16 compressor and indexer weights) ran all 16 accumulators whatever the block size:
   `GemvTMG` runs token groups over sub-groups (`OWN_MT_TGU=2`).
3. The stream mix's double-precision dot rows ride in q_a's and the router's launches (`OWN_MT_RIDE=1`, as the
   one-token path's `OWN_NORM_DOTS=0` form).
4. Token-group size per block size (`OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3`; checked blocks of 4: groups of 2 25.0 ms, of 1
   26.9, of 4 25.3; blocks of 6: groups of 3 30.5, of 2 31.8).
5. `dsp.fc` (15360 columns) packed for the block-read Q8_0 rows (1.05 -> 0.18 ms per round).
6. Small row launches (norms, mix finishes of a few tokens) one sub-group per work-group (`OWN_MT_RWG=128`): the
   512-wide groups put all of a block's norm sub-groups on one core (25.0 -> 24.4 ms for a block of 4).

| check cost, all guesses right (prompt 1) | ms per round |
| --- | --- |
| one-token step (for comparison) | 13 |
| block of 3 | 23.0 |
| block of 4 | 24.4 |
| block of 5 | 28.8 (before 6) |
| block of 6 | 29.6 |

| 3K prompt, 256 tokens (`OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3 OWN_MT_RIDE=1 OWN_MT_RWG=128`) | tok/s | tokens per round | guesses kept |
| --- | --- | --- | --- |
| plain | 68.7 | 1 | - |
| k = 2 | 78.7 | 2.20 | 60.2 % |
| **k = 3** | **86.8** | 2.55 | 51.7 % |
| k = 4 | 80.6 | 2.68 | 42.7 % |
| k = 5 (before 6) | 77.0 | 2.80 | 36.4 % |

Prompt 1 (a short chat answer, 43 tokens to the end of sentence): 75.8 tok/s at k = 3 vs 77.0 plain (2.15 tokens
per round). The 3K and 10K document prompts keep 38-52 % of the guesses (10K, k = 5, before 2-6: 73.7 vs ~69 tok/s
plain). The first acceptance numbers came from 64-token answers and moved by +-0.3 tokens per round between k
values: use 256 tokens or more. The runner first kept writing after a kept end-of-sentence guess (fixed: the text
ends there). Summaries `round16-e48..e53-summary.txt`, scripts `round16-scripts/`.

Profile of a k = 3 round at 3K (cards 2 and 0, `OWN_GPROF=2`; 28.7 ms of kernels per round incl. the draft): the
card-to-card exchanges are 3.1 ms on card 2 and 5.5 ms on card 0. Cards 2 and 5 carry two of the eight attention
groups (heads 16, o_a groups 2; the others one), so their q_b, attention core and o_a take about twice as long
and the other cards wait for them at the next exchange. Routed experts 6.7 ms, dense rows ~8 ms, the pre-norms
of 4 tokens 1.4 ms (17 us each: all 16 sub-groups of 4 tokens in one 512-wide work-group, so on one core: next
round spreads them, `OWN_MT_RWG`).

## 23. Five kinds of prompts; guess as many as the draft is sure of; row blocks: ~86 -> ~92 tok/s median, text identical (2026-11-10 01:35-03:15 EST)

**Prompts.** One short chat prompt per class the realistic suite asks for (code, prose, analysis, operations,
documentation), written for these runs and unchanged since: `data/dsv41-bringup-20261109/spec-prompts/`
(README there; ids made with `tools/mk_chat_ids.py`). Each answer runs to its end of sentence or 512 tokens and is
checked against the plain run token for token (`OWN_VERIFY_REF`). Every run below: **SAME AS the plain run**. These
are lab screening runs (one run per prompt, the engine's own clock over the whole answer), not the realistic-suite
gate (99 intervals after the first token, served).

**How sure the draft is, and when to stop guessing.** The draft's top probability for each guess is well
calibrated: over 1,163 rounds of five guesses on the six prompts (`round17-spec-conf/e57-*`, `OWN_SPEC_CONF=1`),
first guesses it gave 0.99 or more were right 98 % of the time, 0.5-0.7 52 %, under 0.3 12 % (later guesses
alike, counted where the guesses before them were right). Whether one round's guesses are right says nothing
about the next round's. A simulator over those logs with the measured round costs (`round17-scripts/simk.py`;
fixed 2 guesses 84.5, fixed 3 80.4) picked the rule now in the runner: check the leading guesses while the
running product of their probabilities stays at or above `OWN_SPEC_TAU` (0.4 and 0.5 89.9, 0.6 88.5), up to
`OWN_SPEC=5`; `OWN_SPEC_KMIN=0` lets a round check no guess
at all (a one-token block step, which needs token groups of 1 for blocks of 1: `OWN_MT_TGM=1:1,...`).

| measured round cost, short context (draft + check) | ms |
| --- | --- |
| plain one-token step | 13.8 |
| 0 guesses (block of 1 + draft) | ~17.1 |
| 1 guess | 22.1 |
| 2 guesses | 24.3 |
| 3 guesses | 28.0 |
| 4 guesses | 32.5 |
| 5 guesses | 33.3 |

**Row blocks** (`DenseRowsGR`, `GemvQ8P::rowgr` / `GemvQ6KP::rowgr`): a sub-group computes R rows of a weight
matrix for its token group at once, so each activation value is read once for R rows. Each row's sum keeps the
row-at-a-time kernel's expressions and order (bitwise: traces identical after blocks of 16 with R = 4 on every
matrix, and after blocks of 5). It only pays where a card holds many rows: `tools/bench/bench_dense_rowblock.cpp`
(`round17-dense-rowblock-bench.txt`), 4 tokens, Q8_0 1280 x 8192 rows 70 -> 51 us, 1280 x 4096 39 -> 30 us, but
4096 x 864 and smaller lose (too few sub-groups to fill the card). Runner: `OWN_MT_TGR=m:R,...` per block size,
`OWN_MT_TGR_ROWS=4096` (only matrices with that many rows on the card), `OWN_MT_TGR_FMT` (1 Q8_0, 2 Q6_K, 3 both),
`OWN_MT_TGR_DRAFT` (also in the draft's matrices). Check cost per round -0.9 to -1.2 ms. Bench lesson: the first
"cold" timing flushed the cache by writing a large buffer, and the dirty lines were written back during the timed
launch (one-token rows showed 250 GB/s); evict by reading only.

**Draft experts** (`RoutedMXFP4N<NB>`, `OWN_DR_MXN=1` default): the draft's MXFP4 expert rows with the block count
fixed at build time (160 for 5120 columns, 72 for 2304) and the block loop unrolled by 8, loads first. Same sums
in the same order; the guesses are identical. Draft -0.13 ms per round.

**Stream-mix finish** (`HcMixFinishSG` form 1, `OWN_HC_FIN=1`): the 4 x 4 Sinkhorn finish (20 rounds, precise
divides) ran its row and column sums through sub-group reductions; form 1 broadcasts each of the 16 values from a
fixed lane and sums them in the same order. `tools/bench/bench_hc_finish.cpp`: 0 of 98,304 values differ over
4,096 random sets; one sub-group 12.50 -> 7.29 us. Plain 128-token runs 75.5 / 76.3 -> 76.8 / 76.6 tok/s;
traces identical.

| tok/s, whole answer to end of sentence or 512 tokens | code | prose | analysis | ops | docs | 3K document |
| --- | --- | --- | --- | --- | --- | --- |
| plain (one token per step) | ~72-77 | | | | | 68.7 |
| 3 guesses every round (section 22's best) | 88.7 | 67.9 | 94.4 | 83.3 | 88.5 | 90.2 |
| tau 0.5, at least 1 guess | 91.6 | 72.3 | 98.9 | 88.3 | 90.7 | 95.4 |
| tau 0.5, 0 guesses allowed | 89.3 | 73.6 | 101.3 | 89.6 | 91.9 | 95.2 |
| **+ row blocks (rows >= 4096)** | **92.2** | **77.0** | **104.0** | **92.4** | **95.2** | |

(First two rows `round17-e58-summary.txt` on build tp46, the rest `round17-e60-summary.txt` on tp49; same session,
one run each; this host drifts about 3 % back to back.) Median over the five classes: 92.4 tok/s, against ~72.5
plain, +27 %. Prose is the hardest for the draft (2.0 tokens per round at 0 guesses allowed, vs 2.9 on analysis).

**Which row blocks** (`round17-e61-summary.txt`, build tp51, six prompts x four settings, all SAME): both formats
(`OWN_MT_TGR_FMT=3`, the default) beat Q8_0 only by 1-2.5 % on every prompt; leaving the draft's matrices out
(`OWN_MT_TGR_DRAFT=0`) saves 0.1 ms of draft but is not faster overall; `OWN_HC_FIN=1` adds about 1 %. Kept:
`OWN_MT_TGR_FMT=3 OWN_MT_TGR_DRAFT=1 OWN_HC_FIN=1` (the e61 numbers are 1-3 % under e60's on some prompts: same
session, drift).

**Ahead-of-time build** (`round17-e62-summary.txt`): the first run of a new binary used to compile its kernels on
the cards for ~5.5 minutes (one card at a time fills the driver's cache). Built with
`-fsycl-targets=intel_gpu_bmg_g31` (7.5 minutes on the CPU, 98 MB binary, while the cards run something else), the
first run takes 30 s including the 30 s weight upload; traces identical (blocks of 16 with row blocks on every
matrix, blocks of 5), 128-token answers identical, 76.8 / 76.7 tok/s plain (the JIT build 76.8 / 76.6). Builds
are ahead of time from now on.

**Expert kernels at one token** (`tools/bench/bench_routed_m1.cpp`, card 0, the six-card shapes: gate + up 12 x 384
rows of 20 blocks, down 6 x 864 rows of 9 blocks, 6 random experts of 384 per launch; in `round17-e62-summary.txt`):
- Their machine code is already lean: IQ2_XXS is 7 ALU instructions per 32 weights (rotate, and-or, local load,
  multiply, shift, and-xor, multiply, add; the compiler already uses 3-input logic ops), IQ2_S 10.
- R rows per sub-group with the activations read once for all R (`RoutedIQ2XXSR`, bitwise equal): slower (R = 2
  33.2 vs 32.1 us, R = 4 45 us). The kernel is not limited by cache reads; it is ALU-bound. Closed.
- A lane-group broadcast (`select_from_group(sg, v, k + (lane >> 3))`, 16-bit pre-shifted indices) does not
  become a free register region: the compiler emits indirect-register moves (`r[a0.0]`) and more instructions
  (`tools/bench/probe_lane_group_region.cpp`). Closed without inline assembly.
- Work-group count for gate + up: 96 groups (1,536 sub-groups, exactly 3 rounds of 4,608 rows) beats the
  engine's 128 by 6-7 % on IQ2_XXS / IQ2_S / IQ3_XXS / IQ2_XS (29.1 vs 31.2, 42.5 vs 45.4 us); IQ1_S is best at
  128 (50.1 vs 56.3). Down: 128 is best or within noise. (`OWN_PAIR_WG` sets all formats at once.)

**Where a guessing round goes** (3K document, `OWN_GPROF=2`, `round17-e61-spec-round-profile-card{0,2}.txt`, 23.7
ms of kernels per round on both cards, 1,400 launches): routed experts 5.3 ms, exchanges 2.7 ms on card 2 but
4.5 ms on card 0, the draft's MXFP4 experts 0.78 ms, the attention core ~1.9 ms, BF16 indexer / compressor rows
0.9 ms, token norms 0.9 ms (83 launches of 10.6 us: a 160-long chain of double adds is ~4.2 us of it), the
draft's `dsp.fc` (15,360 columns, every card the whole matrix) 0.32 ms, the Q2_K expert layer 0.2 ms. Card 0
waits ~1.8 ms more per round in exchanges than card 2: cards 2 and 5 carry two of the eight attention groups.
Evening that out needs the attention outputs exchanged before o_a (an extra all-gather of 32K floats per
token, ~15-30 us per layer) against ~26 us per layer saved: not worth it.

## 24. Three small levers from section 23's profile: ~92 -> 95.4 tok/s median, text identical (2026-11-10 03:15-04:30 EST)

Each change is a default-on switch whose sums are the old kernel's in the old order; every run below passed the
trace gates (blocks of 16 and 5, one token: `TRACE_IDENTICAL`, `IDS40_SAME`), the plain 128-token answers
(`SPEED128_SAME`) and printed `SAME AS the plain run` for every guessing answer. Builds tp52-tp54, ahead of time.

| tok/s, whole answer (end of sentence or 512 tokens) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dsp.fc on every card (section 23's form) | 89.77 | 75.57 | 101.75 | 91.72 | 94.32 | 91.72 | 97.63 |
| **dsp.fc split** | 93.91 | 78.36 | 105.96 | 94.45 | 97.30 | 94.45 | 99.34 |
| dsp.fc split + gate / up 96 work-groups | 93.35 | 78.15 | 105.31 | 94.13 | 96.97 | 94.13 | 98.08 |
| Q2_K experts generic (tp53, off) | 91.33 | 76.11 | 103.33 | 92.45 | 94.46 | 92.45 | 101.22 |
| **Q2_K experts fast** | 94.08 | 78.61 | 106.72 | 94.97 | 97.79 | 94.97 | 101.80 |
| BF16 rows generic (tp54, off) | 94.00 | 78.88 | 106.76 | 94.54 | 97.82 | 94.54 | 101.55 |
| **BF16 rows by block reads** | 94.76 | 79.62 | 107.54 | 95.41 | 98.70 | **95.41** | 102.34 |
| BF16 rows generic again (A-B-A) | 94.22 | 79.06 | 106.66 | 94.72 | 97.89 | 94.72 | 101.82 |

(`round18-e63-summary.txt`, `round18-e64-summary.txt`, `round18-e65-summary.txt`; one run each, interleaved
per prompt; each block of rows is one session.)

- **dsp.fc split** (`OWN_DR_FC_SPLIT=1`): the draft's input projection (15,360 columns) by model rows like
  attn_output_b, its rows all-gathered in `dr_inject`, instead of every card reading the whole matrix. Draft
  3.29-3.40 -> 3.07-3.10 ms per round, and the check 0.2-0.8 ms less (the feature projection runs in the check
  step).
- **Gate + up work-groups 96** (`OWN_PAIR_WG=96 OWN_PAIR_WG_IQ1=128`, section 23's bench): plain 128-token
  answers +0.5-0.9 % (77.57 / 77.32 vs 76.88 / 76.93) but every guessing answer slower. Closed; 128 stays.
- **Q2_K experts** (`RoutedQ2KF<NB>`, `OWN_Q2K_FAST=1`): layer 0's unpacked Q2_K expert rows with the block
  scales read once per block and every lane on its own 8 weights; `tools/bench/bench_routed_m1.cpp ONLY=q2k`,
  0 of 559,872 values differ at M = 1, 2, 3, 5, 16; M1 73.3 -> 19.4 us, M4 259 -> 65, M16 1026 -> 265
  (`round18-e63c-q2k-kernel-bench.txt`). The round profile has the kernel at 185 -> 50 us per round, but the
  guessing answers gained 0.6-0.8 ms of check per round: more than the kernel time (not explained yet).
- **BF16 rows by block reads** (`GemvH16P` for BF16 matrices of 256/512/1280/5120 columns, `OWN_BF16_ROWS=1`):
  BF16 storage is the upper half of the f32 value, so the 16-bit rows kernel reads it unchanged (same lane order,
  same tree sums as `GemvT<BF16>`; NaN payloads aside). `tools/bench/test_rows_mt.cpp ONLY=bf16h`: 59 checks
  PASS, 0 values differ, no stray writes (`round18-e65pre-bf16h-rows-check.txt`). Plain 128-token answers 78.07
  / 77.88 vs 76.94 / 76.46. The run order does not explain the gains: the generic rows run again after them give
  the first run's speed within 0.3 %.
- Round profile, 3K document, card 2 (`round18-e65-spec-round-profile-card2.txt`): 22.32 ms of kernels per round
  (23.22 in `round18-e63-spec-round-profile-card2.txt`); the generic BF16 rows (0.86 ms) are gone.

**The vocabulary head is slow in row blocks** (`tools/bench/bench_q6k_rows.cpp`, card 0, the head's 21,547 Q6_K
rows of 5,120 columns per card, cold, `round18-e65pre-q6k-rows-bench.txt` and
`round18-e66pre-q6k-head-groups-bench.txt`): the production form for blocks of 2-6 tokens (4-row blocks, rows
>= 4096, section 23) runs 459-651 us; token groups without row blocks run 184-305 us (6 tokens: 651 vs 305;
one group of all 6 tokens 457), every value equal. The round profile shows the same: the head's row-block launches are
1.07 ms per round on card 2 (`round18-e63-spec-round-profile-card2.txt`). A loads-first form of the row kernel (`Q6KAll`) is 15 % faster at one token (169 vs 199 us) and
equal at three. Q8_0 matrices keep their row blocks (`tools/bench/bench_dense_rowblock.cpp`: one group of 5 or 6
tokens is no faster than groups of 3 in 4-row blocks, `round18-e66pre-q8-rowblock-g56-bench.txt`).

**The head without row blocks on six cards: slower** (build tp56, `OWN_MT_TGW_ROWS=16384` with token groups
`OWN_MT_TGWM` 2:2, 3:3, 4:2, 5:3, 6:3; `round18-e66-summary.txt`, `round18-e67-summary.txt`). Every value is the
same (traces identical, every answer SAME), and the head itself is faster in the round profile (card 2: 1.07 ->
0.59 ms per round), but in e67 (off / on interleaved three times on three prompts) every "on" run is slower:
draft -0.12 ms, check +0.5-0.7 ms per round (code 92.94 / 95.06 / 95.25 off vs 93.26 / 93.05 / 93.03 on;
analysis 107.48 / 107.30 / 107.66 vs 105.11 / 105.09 / 105.16). The two round profiles
(`round18-e67-spec-round-profile-card2-{off,on}.txt`) show why: with the head faster, every OTHER kernel is 3-5 %
slower (norms 10.22 -> 10.71 us, attention output 20.7 -> 21.8, IQ1_S experts 86.8 -> 91.5, exchanges 15.9 ->
17.2), the signature of a lower clock, not of the kernels. Each card has a 230 W power cap (275 W on 03 and 83)
over a short window (hwmon `power1_cap`, `power1_cap_interval`).

Measured in e68 with a read-only sampler (`round18-scripts/tools/gpu_sampler.py`: every ~14 ms on all six
cards, `act_freq`, throttle reasons, `energy1_input`; per-run decode windows from `tools/tele_runs.py`,
`round18-e68-telemetry-per-run.txt`): with the head's token groups on, the four 230 W cards (0000:23, 43, a3,
e3) average 2,574-2,654 MHz over the whole answer (306-478 samples per run under 2,700 MHz), while the two 275 W
cards stay at 2,800; head off, all six run 2,782-2,800. The slower cards draw LESS power (168-193 W against
188-217 W off on the same four cards) and report no throttle reason during those runs, so it is not the power cap as such; the card's
own clock choice for this mix of work, cause unknown. Off runs do flag `pl2` (short-window power limit) on
0000:43 and 0000:e3 (537 and 234 samples in the campaign, mostly on the analysis prompt) with the clock still at
2,785-2,800. The switch is now off by default (`mt_tgw_rows = 0`, build tp58). **Bench rule from this:** a
single-card bench runs on a 230 W card (SYCL index 2 = 0000:43) with the sampler on; card 0 (275 W) hid this.

**Q6_K rows of 1-3 tokens load every block first** (`Q6Seg<NB, NT>`, build tp57, e68): bitwise by construction
(the bench's `Q6KAll`, same products in the same order); every e68 gate passed and every answer SAME. Code 95.09
/ 95.10, prose 79.67 / 79.72, analysis 107.67 / 107.70, against tp56 (head off) 92.95 / 95.35, 77.58 / 79.83,
107.80 / 107.80 (`round18-e68-summary.txt`). Never slower than the faster tp56 run of the same prompt, and all six
tp57 runs were in the fast mode below. Adopted.

**Two speeds of the same build.** About a quarter to a third of tp56 runs (and earlier builds) are ~2.3 % slower
than the others with identical output (code_off1 92.95 vs code_off2 95.35: check 18.66 vs 18.11 ms per round).
The slow runs have the same clocks (2,792-2,800 MHz) and draw 3-4 W less per card, a stall rather than a clock.
tp57's six runs were all fast; perhaps loading the head's blocks first hides the memory delay that the slow mode
adds. Not settled; later campaigns run each setting twice, interleaved, and take medians.

**Uneven row shares: slower** (`OWN_TP_WEIGHTS`, e66). Cards 2 and 5 take fewer expert / shared-expert /
output-b / engram rows (weights 875 or 750 against 1000): every value the same (traces identical with 750, plain
answers and every guessing answer SAME), but 0.6-1.0 % slower at 875 and 1.5-4 % slower at 750. The cards meet
at every exchange, so extra attention work on cards 2 and 5 can only be balanced inside the same stretch between
two exchanges; the moved rows sit in the FFN stretch, where the other four cards then become the slow ones. At
750 the four other cards also had only 0.86 GiB free after loading (3.19 equal). The switch stays (default
equal; it may suit other card mixes). Also from e66: the same setting run first and fifth on a prompt differed by
up to 2.7 % (prose 77.50 vs 79.57), so single runs cannot settle effects under ~1 %; e67 and later interleave.

## 25. The draft's experts packed and grouped: ~95.5 -> 97.2-97.7 tok/s median, text identical; Q8_0 loads-first; host threads (2026-11-10 05:00-06:25 EST)

**Q8_0 rows** (`tools/bench/bench_q8_rows.cpp`, card 2 = 0000:43, 230 W, cold, with the sampler;
`round18-e69pre-q8-rows-bench.txt`, `round18-e69pre-q8-rows-mt-bench.txt`). `Q8All<C, NT, SQ>` is `rowg` with SQ
quant words per load segment (production 8, or 6 at 2,304 columns); every arm bitwise equal to production.
Loading every word first (SQ = all):

| shape (per card) | 1 token | groups of 2 | groups of 3 | 5 tokens (3 + 2) |
| --- | --- | --- | --- | --- |
| 5120 x 1024 | 12.8 -> 26.3 us | 17.2 -> 14.8 | 22.4 -> 16.7 | 24.0 -> 20.9 |
| 5120 x 384 | 8.1 -> 19.9 | 12.3 -> 11.3 | 17.1 -> 14.3 | 17.6 -> 15.3 |
| 4096 x 864 | 9.1 -> 13.3 | 12.7 -> 21.2 | 16.6 -> 13.5 | 19.9 -> 17.1 |
| 8192 x 864 | 15.7 -> 15.7 | 23.1 -> 19.6 | 30.4 -> 24.4 | 35.9 -> 29.2 |
| 2304 x 864 | 6.2 -> 7.1 | 8.0 -> 9.6 | 9.9 -> 11.6 | 12.6 -> 14.3 |
| 1280 x 4096 (already all) | equal | equal | equal | equal |

Two tokens stay in groups of one (13.4 us for 5120 x 1024 against 14.8 in one group of 2). `Q8Seg<C, NT>` now
takes all words for groups of 3 on rows of 32+ words and groups of 2 on rows of 40+ words (build tp59); one token,
2,304 columns and groups of 2 on 4,096 columns keep their segments.

On six cards it changes nothing measurable (e69, `round18-e69-summary.txt`; tp58 = tp57 with the head's token
groups off by default, tp59 = tp58 + `Q8Seg<C, NT>`; gates passed, every answer SAME, same guesses kept):

| tok/s | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tp58, round 1 | 92.83 | 77.56 | 105.07 | 92.99 | 95.95 | 92.99 | 101.18 |
| tp59, round 1 | 95.52 | 79.65 | 107.84 | 95.55 | 98.64 | 95.55 | 103.85 |
| tp58, round 2 | 95.26 | 79.58 | 107.70 | 95.64 | 98.78 | 95.64 | 103.86 |
| tp59, round 2 | 95.21 | 79.82 | 107.73 | 95.53 | 98.83 | 95.53 | 103.70 |

Round 2 is within 0.3 % on every prompt. All six tp58 runs of round 1 were in the slow mode of section 24 (check
+0.56-0.62 ms per round, the same 2,777-2,800 MHz clocks, ~4 W less on every card:
`round18-e69-telemetry-per-run.txt`), and none of round 2. Kept (bitwise, faster on one card, neutral here).
A lesson from this campaign: two CPU builds ran beside the first part of round 1 (on CPUs 14-15, one of which also
carried a card thread). The docs and 3K tp58 runs came after both had ended and were still slow, so the builds do
not explain the slow mode alone, but builds now wait for campaigns to end.

**The draft's MXFP4 experts packed and grouped by expert** (`OWN_DR_MXP=1`, default on; build tp60). The draft
read its experts as raw 17-byte blocks, one sub-group per (slot, row), with byte loads (`RoutedMXFP4N`: 166 us
gate + up, 92 us down per stage, three stages per round). Now the upload packs them (`pk41` MXFP4: per 256 columns
32 lane words of 8 nibbles, then the scale bytes; the same size) and `RoutedMXFP4U` = `ops41sycl::RoutedU` with a
new format (`RUFmtMXFP4`, `ops41draft`): the block's slots that picked the same expert share one read and decode of
its rows (`ExpertGroupM`, once per stage), each slot keeps its own sum in the old order, and the lanes are summed
by `reduce_over_group` as before (`RoutedU` gained a slots-per-token parameter, 3 for the draft, and two format
traits: `SGR` for that reduction, `CLAMP_EXP` for the old kernel's expert-id clamp; the target's kernels are
unchanged). `tools/bench/bench_draft_mxfp4.cpp` (card 2, cold, `round18-e70pre-draft-mxfp4-bench.txt`): every
output bitwise equal in all three expert patterns; gate + up 168 -> 94 us with 15 different experts, 167 -> 60
with 7 (a draft-like block), 167 -> 71 with 3; down 94 -> 50, 93 -> 40, 92 -> 37; the grouping launch 2.2-3.2 us.
(The bench's first version timed the old kernel on an eighth of each row: its `NB` counts blocks of 32, the new
format's counts groups of 256.)

On six cards (e70, `round18-e70-summary.txt`; gates passed, every answer SAME, the same guesses kept with and
without, so the draft's outputs are unchanged): draft 3.06-3.09 -> 2.55-2.62 ms per round.

| tok/s (tp60) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OWN_DR_MXP=0`, round 1 | 95.29 | 79.76 | 107.74 | 95.77 | 98.76 | 95.77 | 103.95 |
| **`OWN_DR_MXP=1`, round 1** | 97.02 | 81.23 | 109.63 | 97.71 | 100.71 | **97.71** | 105.59 |
| `OWN_DR_MXP=0`, round 2 | 95.16 | 79.53 | 107.88 | 95.53 | 98.54 | 95.53 | 103.72 |
| **`OWN_DR_MXP=1`, round 2** | 96.93 | 81.07 | 109.82 | 97.23 | 100.37 | **97.23** | 105.36 |

(The MXP=0 rows ran with the threads pinned, see below; pinned and unpinned MXP=1 runs differ by 0-2 %.)

**Card threads pinned to cores: slower** (`OWN_TP_PIN=c0,..,c5[,main]`, default off). On this host the six card
threads float; CPU n and n + 8 share a core, and the cards' interrupts are taken on CPUs 3, 4, 6 and 8
(`/proc/interrupts`: 0000:e3 -> 3, a3 and 83 -> 4, 03 and 23 -> 6, 43 -> 8). Pinned to CPUs 0-5 with the main
thread on 6, plain answers 74.94 / 75.54 vs 78.13 / 77.91 tok/s unpinned, guessing answers the same to 2 % slower
(e70). Left off; a layout that avoids the interrupt CPUs is untested. The host-time profile (`OWN_TP_HOSTPROF`,
plain steps) shows every card thread busy for the whole step and never blocked in its queue wait (12.8 ms per step
unpinned, 13.3 pinned): the threads spin, in the driver's waits or ours, so where they run matters. (Correction: that profile counts only
our queue wait as blocked; the head's final copy-back wait counts as busy, so "busy the whole step" does not show
the threads are the limit.)

**The head without row blocks for blocks of 5 only: slower, closed** (e71, `round18-e71-summary.txt`,
`round18-e71-telemetry-per-run.txt`; tp60, `OWN_MT_TGW_ROWS=16384 OWN_MT_TGWM=1:0,2:0,3:0,4:0,5:3,6:0`, so the form
runs once per round, in the draft's head). Every answer SAME. The draft got faster (2.57-2.61 -> 2.37-2.41 ms per
round), but the check got slower (+0.4-0.55 ms): the four 230 W cards ran at 2,639-2,665 MHz for the whole run
instead of 2,740-2,800, as with the form on every block size (e67/e68). One launch of that form per round is
enough to bring the clocks down.

| tok/s (tp60) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| row blocks, round 1 | 96.87 | 80.99 | 109.57 | 97.18 | 100.58 | 97.18 | 105.41 |
| head-5 groups, round 1 | 95.29 | 79.96 | 108.19 | 95.99 | 99.01 | 95.99 | 103.90 |
| row blocks, round 2 | 96.79 | 81.08 | 109.87 | 97.34 | 100.51 | 97.34 | 105.56 |
| head-5 groups, round 2 | 95.69 | 80.08 | 108.16 | 96.02 | 99.20 | 96.02 | 103.94 |

No run in e71 was in the slow mode (all 12 row-block runs within 0.4 % per prompt).

## 26. The "slow mode" is the engram table's rows missing from the file cache; asking for them sooner and later: a new prompt's cost 2.4-2.6 % -> 0.2 %, median ~97.5 -> ~99.1 tok/s (2026-11-10 06:40-09:10 EST)

**What it was.** Layers 1 and 14 (engram) read 24 hashed rows per token (one Q5_K block of 176 bytes each) from the
135 GB table in shard 6 on the NVMe, through `mmap`. A row that is not in the file cache costs a disk read inside
the step, and the card waits for the host. New per-run line (tp61 on): `host io during decode: X MiB read from
disk, N major page faults; engram rows U us per step and card` (bytes from `/proc/self/io`, host time from the
start of the card thread's row upload to its end: hashes, reads, decode, copy).

A CPU-only bench of the read pattern (`round18-scripts/bench_eng_io.cpp`, 240 rows = one 5-token block, random
rows of the real shard): rows already cached, `madvise(WILLNEED)` on all 240 takes 43 us and reading them 0.2 us;
new rows read one after another 26.9 ms; new rows with `madvise` first (the engine's way) 614 us of `madvise` +
293 us of reads.

**Evidence.** The first runs of each prompt after a build (e72 `_b1`, e73 `_w0`) read 40-123 MiB from disk (40 for the 256-token 3K answer), spend
0.74-0.80 ms per step on the rows (0.30-0.38 warm) and run 1.9-3.2 % slower with 0.5-0.7 ms more check per
round: the "slow mode" of sections 24-25 (same clocks, a little less power: the cards wait). The same prompts read
the same amount again after the next build (code 94.4 / 94.3 MiB, prose 123.3 / 123.3, analysis 78.0 / 78.0 in
e72 / e73): the build's memory use pushes the rows out of the cache. The second run of a prompt reads 0 MiB.
(Section 24's unexplained extra check time in e63, 0.6-0.8 ms per round, is the size of this effect and may
be it.) The first plain 128-token run after a build is slowed too: 75.00 tok/s, 15.9 MiB, 570 us
per step on the rows; the next one 78.22, 0 MiB, 133 us (e73 `p1x`/`p1b`).

**Fairness.** Every guessing number before this section was measured on prompts that had run before, with their
rows cached. A prompt the engine has never seen pays the reads in its first answer (the lab's gate wants cold
first responses). Twelve new prompts (`round18-fresh-prompts/f1-f12`, never run before), each answered twice with
one setting: the old way, the first answer is 2.1-2.6 % slower than the second (median 0.976, +0.54 ms check per
round); with `OWN_ENG_EARLY=1`, 0.4-0.7 % (median 0.995, +0.11 ms). Both answers of every prompt are the same
text. Table: `round18-e73-fresh-prompts-table.md`.

**`OWN_ENG_EARLY=1`** (tp62): (a) the anchor's 48 rows (its position is known before the draft runs) are asked
for in `draft_tp` right after the cards start the draft, so their reads run behind it; (b) a block's other rows
are split over the six card threads, each asking for its share (every sixth row) and waiting on it before
reading all rows, instead of the main thread's 240 serial requests; (c) `MADV_RANDOM` on the table mapping, so a
miss reads its page only, not 128 KiB around it. Trace gates (blocks of 16 and 5, one token) `TRACE_IDENTICAL`
/ `IDS40_SAME`, plain 128 `SPEED128_SAME`, every guessing answer SAME (e73, `round18-e73-summary.txt`). With the
rows cached it also helps a little (rows 340 -> 288 us per step):

| tok/s (tp62, rows cached) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first runs after the build (rows read from disk) | 94.55 | 78.54 | 107.29 | 94.77 | 98.08 | 94.77 | 103.17 |
| default, round 1 | 97.04 | 81.11 | 109.75 | 97.52 | 100.68 | 97.52 | 105.39 |
| **`OWN_ENG_EARLY=1`, round 1** | 97.45 | 81.72 | 110.47 | 98.06 | 100.99 | **98.06** | 105.98 |
| **`OWN_ENG_EARLY=1`, round 2** | 97.41 | 81.47 | 110.34 | 98.27 | 100.98 | **98.27** | 106.03 |
| default, round 2 | 97.13 | 81.10 | 109.79 | 97.40 | 100.65 | 97.40 | 105.61 |

**Rows decoded on the cards (`OWN_ENG_DEV=1`, tp61): a GPU fault in one run; off.** Each card thread decodes the
same rows on the host (about 133 us per one-token step, 300-440 us per checked block); `OWN_ENG_DEV` copies the
raw 176-byte rows to each card and decodes them there with `EmbedRowA`'s decode (`EngRowsA`). Its gates passed
bitwise (e72). In its second guessing run (code), card 0000:43 faulted (06:49:01): `Suspend fence, guc_id=7,
failed to respond`, then a timed-out job on the driver's own copy queue (`bcs0`, "no process"), `VM worker error:
-62`, a GT reset; the run ended with `UR_RESULT_ERROR_OUT_OF_RESOURCES`. A job of ours did not pause when the
driver needed to move a buffer; the new code's pinned host buffers (`malloc_host`) are the suspect, not proven.
The runner was paused between runs, the dump saved (`round18-e72-devcoredump-43.txt.gz`, kernel lines in
`round18-e72-fault-kernel-log.txt`), and the six-card health probe passed with a clean kernel log. Its other
three guessing runs finished (SAME). tp63 stages the raw rows in ordinary host memory, as the default path does;
campaigns now stop at the first fault line (the filter gained `timedout job`, `exec queue reset`, `suspend fence`,
`vm worker error`) and log `/proc/vmstat` around every run.

The `/proc/vmstat` logs show why pinned host memory is a risk on this host: memory compaction moves 5,000-260,000
pages during every run (`pgmigrate_success`, `round18-e73-vmstat.txt`), and the driver maps a pinned host buffer
from ordinary process pages; moving one forces the driver to remap it, which needs our running jobs paused, and
ours spin-wait on each other. (Compaction is a host memory setting: not changed.) Background reclaim also frees
about 200 MB of file cache per run with 8-10 GB free, so a prompt's rows can drop out between two of its runs
(e74's `_x1` runs read 60-100 MiB each, right after the same prompts ran cached): read the `host io` line before
comparing two runs.

**`OWN_ENG_LATE=1`, rows decoded on the cards again (tp63; both default on from tp64).** LATE: each card thread
launches the embed and layer 0 first and only then fetches the rows (and asks for its share of the reads), copies
them and pushes the engram projection; layers 1 and 14 are the first to need them, and the embed no longer waits
for its queue. The copy from ordinary host memory returns only when the queue reaches it, so the host now waits
for layer 0 there instead of the card waiting for the host (`engram rows` reads 260-550 us, mostly that wait).
`OWN_ENG_DEV` now stages the raw rows in ordinary host memory (no pinned buffers). Gates for both (traces of
blocks of 16 and 5 and one token, plain 128) identical; 42 guessing answers SAME; no fault line (e74,
`round18-e74-summary.txt`, table `round18-e74-table.md`). Plain 128-token answers: 77.73-78.07 tok/s default,
78.32-78.34 LATE, 78.32-78.43 LATE + DEV.

| tok/s (tp63) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EARLY, round 1 (rows read from disk, see above) | 97.02 | 81.31 | 109.51 | 97.50 | 100.56 | 97.50 | 105.36 |
| EARLY, round 2 | 97.53 | 81.61 | 110.49 | 97.99 | 101.35 | 97.99 | 105.90 |
| EARLY + LATE, round 1 | 97.99 | 82.07 | 111.07 | 98.64 | 101.68 | 98.64 | 106.65 |
| EARLY + LATE, round 2 | 98.08 | 82.07 | 111.15 | 98.75 | 101.55 | 98.75 | 106.43 |
| **EARLY + LATE + DEV, round 1** | 98.36 | 82.37 | 111.63 | 99.03 | 102.05 | **99.03** | 107.16 |
| **EARLY + LATE + DEV, round 2** | 98.22 | 82.45 | 111.59 | 98.97 | 102.09 | **98.97** | 106.97 |

**Defaults from tp64: EARLY, LATE and DEV on** (`OWN_ENG_EARLY=0`, `OWN_ENG_LATE=0`, `OWN_ENG_DEV=0` give the old
way back). tp64 also has `OWN_TP_SPIN_US=n`: the main thread and the card threads wait for each other's hand-off by
polling for up to n us before sleeping. e75 (`round18-e75-summary.txt`, table `round18-e75-table.md`): gates for
the default and for `OWN_TP_SPIN_US=2000` (traces of blocks of 16 and 5 and one token, 40-token answers) identical;
30 guessing answers SAME as the plain run; no fault line. Plain 128-token answers: 77.83-77.96 tok/s the old way
(warm), 78.36-78.40 default, 78.32-78.37 spin.

| tok/s (tp64) | code | prose | analysis | ops | docs | median of 5 | 3K document |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first runs after the build (423 MiB of rows read from disk over the six) | 98.55 | 82.23 | 111.57 | 98.74 | 102.01 | 98.74 | 106.98 |
| **default, round 1** | 98.38 | 82.51 | 111.66 | 99.17 | 102.37 | **99.17** | 107.06 |
| spin 2000 us, round 1 | 98.65 | 82.55 | 111.71 | 99.08 | 102.47 | 99.08 | 106.87 |
| spin 2000 us, round 2 | 98.50 | 82.30 | 111.49 | 99.11 | 102.27 | 99.11 | 106.98 |
| **default, round 2** | 98.50 | 82.42 | 111.43 | 99.03 | 102.21 | **99.03** | 107.14 |

The spin hand-off changes nothing measurable (closed; default 0). Twelve new prompts f13-f24 (never run before),
each answered cold then warm, odd ones the old way and even ones with the defaults (`round18-fresh-prompts/`): every
cold answer equals its warm one; the cold runs read 89-105 MiB from disk each. Old way: cold / warm 0.970-0.977
(median 0.974), the check 0.56 ms per round slower cold (median). Default: cold / warm 0.997-1.004 (median 0.998),
the check 0.03 ms slower. **A prompt the machine has never seen now runs as fast as a repeated one.**

## 27. A larger register file where kernels would spill: guessing ~99.1 -> ~102.1 tok/s median, text identical; prompt reading settings; new long documents (2026-11-10 09:10-11:10 EST)

**Prompt reading settings (e76, tp64, `round18-e76-table.md`).** The 3K document read in blocks of 16, two rounds
(second reversed), each run's first 16 answer tokens checked against the plain answer (17 of 17 the same):

| 3K document, blocks of 16 (tp64) | round 1 tok/s | round 2 tok/s |
| --- | --- | --- |
| default (token groups of 4) | 277.0 | 277.0 |
| row blocks of 4 (`OWN_MT_TGR=16:4`), matrices of >= 4,096 rows | 273.5 | 273.1 |
| row blocks of 4, >= 2,048 rows | 269.7 | 269.6 |
| row blocks of 4, every matrix | 231.3 | 231.2 |
| row blocks of 2, >= 4,096 rows | 277.9 | 279.0 |
| token groups of 3 + row blocks of 4 | 267.2 | 267.4 |
| unpacked rows in groups of 3 (`OWN_MT_TGU=3`) | 276.4 | 276.4 |
| unpacked rows all at once (`OWN_MT_TGU=0`) | 276.6 | 276.7 |

The build log explains the row-block losses: 92 kernel forms spilled registers (`DenseRowsGR<GemvQ6KP<20>, 1, 4>`
145, `DenseRowsM<GemvQ8P<160>, 16, 8>` 398, ...). Kernel time per 16-token block on card 2
(`round18-e76-prompt-3k-profile-card2.txt`): dense weight rows 25.0 ms, routed experts 18.9, exchanges 8.0,
attention 2.8, other 1.3, norms 1.2 (57.2 ms).

**New long documents (never run before): reading them cold costs 0.5 %; `OWN_ENG_AHEAD` removes it.** Eight lab
documents (`round18-fresh-prompts/long/`, 2,246-3,219 tokens), each read cold then warm: on tp64 the cold read is
0.994-0.995 of the warm one (L1-L4); every cold answer equals its warm one. tp65's `OWN_ENG_AHEAD=n` (default 16;
needs `OWN_ENG_EARLY`): while the cards run one prompt block, the main thread asks the disk for the engram rows of
the next n prompt tokens (page-cache hints only, so the rows read later are the same bytes). e77: off 0.995 and
0.995 (L5, L7), on 1.000 and 1.003 (L6, L8).

**The GPU compiler's automatic large register file (tp65).** Built with
`-Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode"`: a kernel that would spill
is compiled again with 256 registers per thread instead of 128 (half as many threads per core). Same instructions,
so the same values (`round18-scripts/grf_test.cpp` shows the switch on a small kernel: 128 registers + 212 spilled
-> 256 + 92). Spill warnings 92 -> 29 kernel forms; build 424 s. e77 (`round18-e77-summary.txt`, table
`round18-e77-table.md`): gates identical (traces of blocks of 16 and 5 and one token, plain 128-token answers);
36 guessing answers SAME as the plain run; no fault line.

| tok/s | code | prose | analysis | ops | docs | median of 5 | 3K document | draft ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tp64, round 1 | 98.54 | 82.35 | 111.63 | 99.23 | 102.09 | 99.23 | 106.84 | 2.57-2.60 |
| **tp65, round 1** | 101.44 | 84.84 | 114.71 | 102.06 | 105.22 | **102.06** | 109.98 | 2.27-2.31 |
| **tp65, round 2** | 101.43 | 85.09 | 114.92 | 102.08 | 104.87 | **102.08** | 110.33 | 2.26-2.31 |
| tp64, round 2 | 98.68 | 82.17 | 111.69 | 99.17 | 102.08 | 99.17 | 106.70 | 2.56-2.59 |

The draft step gains most (2.57 -> 2.28 ms; its expert rows spilled), the check 0.3 ms per round. Plain 128-token
answers lose a little: 78.05-78.18 tok/s against 78.34-78.36 (some one-token kernel now runs with half the
threads). Prompt reading at 3K: 275.6-276.8 against 274.1-275.3.

**Where prompt reading waits (e77, tp65, per 16-token block, `round18-e77-prompt-3k-profile-card{0,2,5}.txt`).**

| card | attention groups | dense rows ms | routed experts ms | exchanges ms | attention ms | other ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 (0000:03) | 1 | 20.30 | 18.48 | 13.32 | 2.17 | 2.46 |
| 2 (0000:43) | 2 | 24.66 | 18.88 | 7.96 | 2.78 | 2.52 |
| 5 (0000:e3) | 2 | 26.06 | 20.18 | 4.92 | 2.94 | 2.66 |

Card 5 sets the pace: it carries two of the eight attention groups (q_b and o_a rows and the attention core
twice) and also runs its expert rows 7-9 % slower than the others; it is the card whose clock drops (2,738-2,792
MHz against 2,800, with throttle reasons logged, `round18-e77-telemetry-per-run.txt`). Every exchange costs it
4.9 ms per block; the other cards wait up to 8.4 ms more for it. Evening the attention groups needs one more
(small, two-card) exchange of head outputs per layer; that is the next lever measured against this table.

## Reproduce

```bash
cd experiments/own-xpu-runtime/engine
ICPX=/opt/intel/oneapi/compiler/latest/bin/icpx
$ICPX -O3 -fiopenmp -std=c++20 -DOWN_RT_HOST_ONLY -I src -I planning/dsv41-fixtures \
  -o cpu_run_v41 planning/dsv41-fixtures/cpu_run_v41.cpp
$ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -I planning/dsv41-fixtures -I src \
  planning/dsv41-fixtures/own_run_v41.cpp -o own_run_v41 -lze_loader
# (the measured builds since section 27 add -fsycl-targets=intel_gpu_bmg_g31 and
#  -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode")
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
# reference: prompt ids -> 40 tokens, state dump, 3-step trace (KV rows BF16 like the engine;
# add OWN_CONTRACT=1 and build with -fp-model=precise -ffp-contract=off for the device's summation order)
OWN_KV_BF16=1 OWN_TRACE=cpu.trc OWN_TRACE_STEPS=3 OMP_NUM_THREADS=16 ./cpu_run_v41 ids.txt 40 ref_ids.txt 4096 \
  <shard 6> /dev/null state.bin
# cards only: prompt ids in, generated ids out (stops at end of sentence)
OWN_PROMPT=ids.txt ./own_run_v41 - 200 out_ids.txt 4096
# every layer split across the six cards (fastest; OWN_GPROF=2 OWN_GPROF_CARD=c profiles card c)
OWN_TP=6 OWN_PROMPT=ids.txt ./own_run_v41 - 200 out_ids.txt 4096
# with the DSpark draft guessing (section 23's settings; OWN_VERIFY_REF=<plain run's ids> checks the text)
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
env OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 \
  OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 \
  OWN_DSPARK=dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf OWN_PROMPT=ids.txt ./own_run_v41 - 512 out_ids.txt 4096
# (build with -fsycl-targets=intel_gpu_bmg_g31 added to skip ~5.5 min of kernel compiling on the first run)
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
   context (compact the live slots).
3. Guessing rounds (profiles in sections 23-24): checking a block of 4 still costs ~1.8x a one-token step. Next:
   the head's 4-row blocks at 2-6 tokens (0.6 ms per round on card 2; the row-block-free form drops the 230 W
   cards' clocks, section 24, even when it runs only for blocks of 5, section 25), token norms inside their neighbours (0.9 ms),
   exchanges folded into the kernels that consume them, the copy of the engram rows without the queue wait
   (section 26: the host now waits for layer 0 there). Closed: the card threads' spinning waits (section 25)
   and polling hand-offs (section 26). The
   attention groups stay uneven (8 over 6 cards: evening them costs an extra exchange). (Done: adaptive guess
   counts, section 23; the batched prompt pass, sections 20-21, 251 tok/s at 3K; dsp.fc split, Q2_K and BF16 rows,
   section 24; the draft's experts, section 25; engram rows asked early and fetched after layer 0, section 26.)
6. Prompt reading (~276 tok/s at 3K, blocks of 16): card 5 sets the pace (two attention groups and a lower
   clock, section 27 table); the other cards wait up to 8.4 ms per 16-token block at the exchanges. Next: split
   the two doubled attention groups by heads between card pairs (one small exchange of head outputs per layer).
   Closed: row blocks and token-group variants for blocks of 16 (section 27, e76); cold reads of new documents
   (`OWN_ENG_AHEAD`, section 27).
4. `compress_ratios`, window and top-k constants are hardcoded in three places; they belong in the profile.
5. A float-exact llama.cpp comparison to remove the remaining noise from section 4; report the nested-loop
   miscompile (IQ2_S, IQ2_XS/f32) upstream with the standalone reproducer shape from the gate.
