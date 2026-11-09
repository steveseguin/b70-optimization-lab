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
- **Not done:** one run on all six cards at once. Two cards are held by the Gemma service that restarts at every
  boot. The model was validated in two halves instead (layers 0-27 on four cards; layers 28-39 + head on two).
- Speed after a first tuning round: about 0.16 s per token summed over the two halves (6 tok/s), from 0.86 s
  when it first ran. The llama.cpp reference screen is 14 tok/s. Section 6.

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

## Reproduce

```bash
cd experiments/own-xpu-runtime/engine
ICPX=/opt/intel/oneapi/compiler/latest/bin/icpx
$ICPX -O3 -fiopenmp -std=c++20 -DOWN_RT_HOST_ONLY -I src -I planning/dsv41-fixtures \
  -o cpu_run_v41 planning/dsv41-fixtures/cpu_run_v41.cpp
$ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -I planning/dsv41-fixtures -I src \
  planning/dsv41-fixtures/own_run_v41.cpp -o own_run_v41
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
# reference: prompt ids -> 40 tokens, state dump, 3-step trace
OWN_TRACE=cpu.trc OWN_TRACE_STEPS=3 OMP_NUM_THREADS=16 ./cpu_run_v41 ids.txt 40 ref_ids.txt 4096 \
  <shard 6> /dev/null state.bin
# all six cards (cards must be empty; the runner refuses otherwise)
OWN_DEBUG=1 OWN_TRACE=dev.trc OWN_TRACE_STEPS=3 ./own_run_v41 state.bin 40 dev_ids.txt 4096
python3 tools/dsv41_trace_diff.py cpu.trc dev.trc
# a subset of cards: OWN_LAYERS=0:28 OWN_HEAD=0 OWN_DEVS=2,3,4,5 OWN_FORCED=ref_ids.txt
#                    OWN_LAYERS=28:40 OWN_DEVS=2,3 OWN_INJECT=cpu.trc OWN_FORCED=ref_ids.txt
```

Long GPU runs go in their own unit (`systemd-run --user`). Check `systemctl is-active
gemma4-26b-q8-quad-backends` first: six-card runs need it stopped.

## Open

1. The six-card run (needs the two Gemma cards).
2. Speed, next levers in order: expert down-projection (30,720 short rows), router selection (one serial
   work-item), engram row prefetch at step start, stream-mix lanes, then fusing the small launches.
3. Prompt pass on the cards (today: CPU reference, roughly a minute and a half for 36 tokens).
4. `compress_ratios`, window and top-k constants are hardcoded in three places; they belong in the profile.
5. f32-activation mode; a float-exact llama.cpp comparison to remove the remaining noise from section 4.
