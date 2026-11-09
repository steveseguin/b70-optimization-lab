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

## Reproduce

```bash
cd experiments/own-xpu-runtime/engine
ICPX=/opt/intel/oneapi/compiler/latest/bin/icpx
$ICPX -O3 -fiopenmp -std=c++20 -DOWN_RT_HOST_ONLY -I src -I planning/dsv41-fixtures \
  -o cpu_run_v41 planning/dsv41-fixtures/cpu_run_v41.cpp
$ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -I planning/dsv41-fixtures -I src \
  planning/dsv41-fixtures/own_run_v41.cpp -o own_run_v41
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
# reference: prompt ids -> 40 tokens, state dump, 3-step trace (KV rows BF16 like the engine;
# add OWN_CONTRACT=1 and build with -fp-model=precise -ffp-contract=off for the device's summation order)
OWN_KV_BF16=1 OWN_TRACE=cpu.trc OWN_TRACE_STEPS=3 OMP_NUM_THREADS=16 ./cpu_run_v41 ids.txt 40 ref_ids.txt 4096 \
  <shard 6> /dev/null state.bin
# all six cards (cards must be empty; the runner refuses otherwise)
OWN_DEBUG=1 OWN_TRACE=dev.trc OWN_TRACE_STEPS=3 ./own_run_v41 state.bin 40 dev_ids.txt 4096
python3 tools/dsv41_trace_diff.py cpu.trc dev.trc
# a subset of cards: OWN_LAYERS=0:28 OWN_HEAD=0 OWN_DEVS=2,3,4,5 OWN_FORCED=ref_ids.txt
#                    OWN_LAYERS=28:40 OWN_DEVS=2,3 OWN_INJECT=cpu.trc OWN_FORCED=ref_ids.txt
```

Long GPU runs go in their own unit (`systemd-run --user`). The Gemma units were stopped and disabled by the
owner on 2026-11-09; if they are ever enabled again they take two cards at boot and the runner will refuse.

## Open

1. Stop at the end-of-sentence token in the runner; a server front end.
2. Speed, next levers: the weight matmuls are now 75 % of the time at 200-330 G elements/s (flat-loop forms for
   Q6_K/Q5_K, which carry the deeper layers, the head and the engram projections); the attention core at short
   context (compact the live slots); top-512 selection on the card for long contexts.
3. Prompt pass on the cards (today: CPU reference, roughly a minute and a half for 36 tokens).
4. `compress_ratios`, window and top-k constants are hardcoded in three places; they belong in the profile.
5. A float-exact llama.cpp comparison to remove the remaining noise from section 4; report the nested-loop
   miscompile (IQ2_S, IQ2_XS/f32) upstream with the standalone reproducer shape from the gate.
