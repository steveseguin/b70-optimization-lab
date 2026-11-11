# DeepSeek V4.1 Flash on six B70: faster forms already on this disk (2026-11-11)

Helper output for `2026-11-11-dsv41-speed-strategy.md` (method rule 6, "read before inventing"). Sources read: our
older engines and research folders (SC117 / packet194 expert diet / packet6-kopt / research/*), the Qwen and
FP8 lanes, oneCCL, llama.cpp at `/home/steve/src/llama.cpp-dsv41-20261108` (upstream 7d7f02875, SYCL and Vulkan),
and the OpenVINO GenAI 2026.4.1 GPU plugin in `/mnt/fast-ai/builds/ov-genai-repro/venv`. Nothing was run on a
card and nothing was compiled for this note. Every gain below is a prediction until its bench says otherwise.

Paths: relative to `experiments/own-xpu-runtime/` unless they start with `/` or `experiments/`; `packetNNN-*` =
`engine/src/stage2/packetNNN-*`; `docs/` and `community/` are at the repo root; `§N` = sections of
`notes/2026-11-09-dsv41-device-load-host-memory.md`.

## In plain words

1. **The biggest local lever is how the cards hand data to each other**, not a kernel. Each of the 160 hand-overs
   per word costs ~12 us because a card must ask "are you done?" across PCIe and then fetch the data (two trips).
   Our own older engine (SC117, on the four-card host) wrote results straight into the other card's memory and
   paid only ~1.4-3.3 us per hand-over. On this host such writes were measured at ~1 GB/s, but only in our
   current setup (one runtime context per card, memory shared by handle). SC117 used one shared native context
   with a driver setting that stops the host-memory copy we feared. One small bench tells us which it is.
   If fast: up to ~1.5 ms of the 11.7 ms word (~12 %).
2. **The expert kernels spend their time on bookkeeping, not on reading weights.** Each lane decodes one weight at
   a time and repeats the index, table and scale work for every weight. Letting one lane carry 4 or 8 of the
   reference's "virtual lanes" (an exact trick our SC117 engine already used, 1074 -> 730 us) shares that work over
   4-8 weights while keeping every sum in the same order. If the instruction count halves: ~0.9-1.2 ms per word
   (~8-10 %). An offline machine-code count tells us before any card run.
3. **A cheaper version of item 1 inside today's setup:** put a stamp inside the data so the receiver needs one trip,
   not two (oneCCL does this). ~0.25 ms per word (~2 %).
4. **Small cleanups:** fold the SwiGLU and expert-sum launches into the exchange launches that follow them
   (~80 launches per word, ~0.1 ms); 64-bit index math in `XchgPull`.
5. llama.cpp and OpenVINO are **not** faster forms of our kernels: their fast paths round the activations to int8
   or fp16, or use fused multiply-add / scale-after-sum orders. What carries over are layouts and structure
   (8-weight grid reads, one-launch MoE with an epilogue, decode-once-into-shared-memory for prompts).
   llama.cpp's own DeepSeek V4 decode is ~60-90 launches per layer against our ~26; SYCL graph replay there is off
   by default and switches itself off on more than one card.

## Our kernels today (card 2, round19 b1 profile, `OWN_GPROF=2`, profiled step 14.0 ms, real step 11.7 ms)

Source: `data/dsv41-bringup-20261109/round19-b1-profiles/dec-card2.txt`; instruction counts from my ISA census of
the production kernels (`/home/steve/dsv41-work/isa-e1`, NB20 minus NB9 builds over 88 chunks, SIMD32 instructions
per 32-weight chunk = per weight per lane). Kernel line numbers are `engine/src/stage2/packet3/kernels/sycl_v41.hpp`
in the working tree of 2026-11-11 (uncommitted changes exist past ~line 3795; lines below 3795 match HEAD 21eec1e85).

| Kernel (our file:line) | Per step on card 2 | Weights/s | GB/s | Instr per weight (int / float / SLM / global / sync) | Rows per sub-group, WG |
|---|---|---|---|---|---|
| RoutedIQ2XXSP<20> gate+up, sycl_v41.hpp:1866-1917 | 15 x 35.2 us | 677 G | 175 | 4.51 / 3.09 / 1 / 0.56 / 1.18 = ~10.3 | 1, WG 512 (16 rows), 128 WGs persistent |
| RoutedIQ2SP<20> gate+up, :1920-1983 | 15 x 51.3 us | 461 G | 148 | 7.92 / 4.24 / ... = ~14.0 | same |
| RoutedIQ1SP<20> gate+up, :2105-2167 | 10 x 52.3 us | 453 G | 88 | 7.80 / 5.15 / ... = ~14.9 | same |
| RoutedIQ2SP<9> down | 15 x 28.1 us | 422 G | | (as IQ2_S) | same |
| RoutedIQ3XXSP<9> down, :1986-2040 | 15 x 25.4 us | 468 G | 179 | 9.23 / 3.64 / ... = ~15.7 | same |
| RoutedIQ2XSP<9> down, :2043-2101 | 6 x 25.2 us | 470 G | | 7.77 / 4.25 / ... = ~13.5 | same |
| GemvQ8P<128/256> dense, :1544-1708 | 27 x 18.1 + 27 x 16.1 us | | ~475-495 | (§31 d2: ~4 per weight-token in the prompt forms) | 1 row per sub-group |
| GemvQ6KP<20> head, :2185-2383 | 1 x 158.9 us | | ~569 | | |
| XchgPull, :5776-5882 | 83 x 12.3 us | | | | nwg = clamp(vec4/512, 4, 64) x 256 (backend_sycl_v41.hpp:2786) |
| XchgP (push), :4494-4545 | 80 x 6.8 us | | | | |
| SwigluBothS :4567 / MoeCombineA :1161 | 40 x 1.10 / 40 x 1.48 us | | | | |

Expert kernels total ~2.86 ms kernel time per step on card 2; exchanges 1.79-2.14 ms on every card (xchg mark, all
six b1 profiles: 1.94 / 1.79 / 2.14 / 1.92 / 1.95 / 2.11). XchgPull costs 11.0-13.3 us on all six cards, so most of
it is transport, not waiting for a late card (a waiting card would show much longer exchanges than the late one).

Why the expert kernels are slow (lane note §11, §23, §31 u1): one weight per lane per chunk, so the index extract,
grid-table read, sign isolate and scale work are paid per weight. The stall sampler said "issue-bound with lean
code": IQ2_XXS active 60.4 % with 31.3 % ALU-pipe waits; IQ2_S 52.8 % with 26.1 % register-dependency waits on the
32 KB table reads. IQ2_XXS runs ~30 cycles per chunk per XVE against an issue floor of ~8-20. They read at
88-179 GB/s of ~600, so bandwidth is not the limit.

The order the reference fixes (`OWN41_ROUTED_ROWS_BEGIN/END`, :1827-1857): lane l owns columns 32c + l, chunks in
ascending order, `sum = sum + v * x` with no FMA (-fp-model=precise -ffp-contract=off), then the xor butterfly
`for w = 16..1: sum += select_from_group(sum, lane ^ w)`. Dense kernels end with `sg_tree32` (:17-24, adjacent
pairs, width 1, 2, 4, 8, 16). **What the order does not fix: which hardware work-item holds which logical lane's
accumulator.** That freedom is what lever L2 uses.

## Ranked opportunities

| # | Lever | Their code | Our code | Lossless? | Most it can win (card 2, of 11.7 ms) | Odds | Proving bench |
|---|---|---|---|---|---|---|---|
| L1 | Direct peer stores in one native Level Zero context + `EnableDeferBacking=0` | packet194 single_device.cpp:25-50, 105-162; research/p2p/direct-store-2026-10-28/RESULT.md:1-40 | backend_sycl_v41.hpp:8-20 (one SYCL context per card), :313-315, :412; XchgP / XchgPull | yes (moves bytes) | ~1.5 ms (~12 %) | unknown: decided by one bench | `xchg_bw_bench` variant with a shared native context, after a host-RAM probe |
| L2 | Packed logical lanes (one work-item carries 4 or 8 reference lanes) in the routed IQ kernels | packet194 dn2_kernels.hpp:12-75; research/decode-next2/RESULT.md ~40-67 | sycl_v41.hpp:1827-2167 | yes if the butterfly is replayed (below) | ~0.9-1.2 ms (~8-10 %) | medium | ISA census (offline) -> `bench_routed_m1` candidate, bitwise vs production |
| L3 | Stamp-in-data ("LL") exchange: one PCIe trip instead of two | oneCCL `/home/steve/src/oneccl-public-qwen27/.../protocol/proto_rt64_128.hpp`:23-47, 133-192, 447-501 | XchgPull :5776-5882 | yes | ~0.25 ms (~2 %) | medium | `xchg_lat_bench` new variant, then `xchg_pull_test` 2,000 iterations 0 wrong |
| L4 | Fold SwiGLU into the activation exchange launch and the expert sum into the h push launch | OpenVINO moe_3gemm_swiglu_opt (mlp_gate_up epilogue); Vulkan ADD_ID/MUL epilogue ggml-vulkan.cpp:14630-14645 | SwigluBothS :4567, MoeCombineA :1161, backend phases ~2940-3130 | yes (same expressions) | ~0.1 ms (~1 %) | high | 3-step trace byte-identical; b1 profile |
| L5 | 32-bit, statically indexed copy math in XchgPull | research/2026-10-25-decode-roofline.md:25-60 (64-bit math emulated: IQ2_S 80.1 -> 33.5 us) | XchgPull copy_seq :5816+ (size_t k, n4, k % n4, runtime b0[d] / b1[d]) | yes | < 0.05 ms | high | `dump_isa.sh` + `isa_census.py` on xchg_pull_test.cpp (look for int64 / indirect moves), then `xchg_lat_bench` |
| P1-P3 | Prompt: decode once per block into shared memory, reuse tiles, transpose reduction | below | below | yes with the order rules below | prompt 2-4x (ceiling estimates in the strategy note) | medium | `bench_dense_m16`, `test_routed_u` |

### L1. Direct peer stores in one native context (the exchange transport)

What we have: every exchange is a launch (~2.4 us) + a flag round trip (~2.5-3 us) + a load round trip
(~5-6 us), one after the other (§21, lines 567-580; §28, around line 1224). Pushes were measured at
~1 GB/s per card "whatever the shape" (`xchg_bw_bench.cpp`, `round15-xchg-bw-bench.txt`). That bench, like the
engine, opens peers' arenas by Level Zero IPC handles into **one SYCL context per card**
(`tools/bench/xchg_bw_bench.cpp:1, 48-67`; `backend_sycl_v41.hpp:313-315, 412`).

What the older engine did: `packet194-expert-diet-engine/single_device.cpp:25-50` creates **one native Level Zero
context for all cards** and keeps per-card SYCL contexts only for the kernel cache (`OWNRT_TP_CARD_CONTEXT`);
`:105-162` `submit_exchange`: the producing kernel stores its rows into the peer, release fence, last-work-group
counter, plain volatile flag store, then each card polls its own local flag. Measured on the four-card host
(`research/p2p/direct-store-2026-10-28/RESULT.md:1-40, 50-62`): added cost 1.43 / 1.63 / 3.33 / 10.98 us at
4 / 10 / 40 / 160 KB (~14 GB/s). The host-RAM shadow that rules out a shared context here was removed there by
`NEOReadDebugKeys=1 EnableDeferBacking=0` (`research/tp/direct-exchange-2026-10-28/RESULT.md:205-222`: shadow
+8.00 -> +0.00 GiB; `INVENTORY.md:63`: 12.6 GiB -> 0.3 GiB, identical results, 603 GB/s matvec).

Why it may not carry over: different PCIe fabric (four-card host, cards 23:00 / 47:00), and our 1 GB/s could be
the fabric itself. Nobody has measured peer stores on TURIND8 from a shared native context, and the lane note §1
measured the 1:1 host-RAM cost of a shared context **without** `EnableDeferBacking=0`.

Exchange sizes today: h (one token) 3,456 bytes per card; the activation exchange ~9.5 KB per card (7 slots);
pulls start at 8,192 bytes (`backend_sycl_v41.hpp:233, 2819-2826`). At SC117's 4-10 KB costs (1.4-1.6 us) all 160
exchanges would be ~0.3-0.4 ms instead of ~1.9-2.1 ms. A store-based exchange can also be done by the producing
kernel (no separate XchgP launch), the step that removed SC117's launch.

Proof, in order (one card-pair first, all host-RAM rules apply):
1. Host-RAM probe: a shared native context over all six cards with `EnableDeferBacking=0`, allocate 1-4 GiB per
   card, read MemAvailable and the xe driver-held memory (as `probe-multicard-buffer-sharing.py` and
   `xe_vram_probe` did). Stop if host RAM moves 1:1.
2. `xchg_bw_bench` with a `--shared-native-context` mode (allocations from the shared context, raw peer pointers,
   no IPC): store GB/s and the 3.4 / 9.5 KB latency against today's 1 GB/s / 6.8 us.
3. If fast: `xchg_pull_test`-style correctness with stores (stale reads inside one persistent kernel needed atomic
   loads in SC117, RESULT.md 50-62).

### L2. Packed logical lanes for the routed expert kernels

Their code: `packet194-expert-diet-engine/dn2_kernels.hpp:12-59` `xxs_packed` (IQ3_XXS): 4 rows per SG32, item t
owns logical lanes 4t..4t+3 of its row, shares the index byte, grid word, sign code and factor across them,
reduces ((l0 + l1) + (l2 + l3)) in registers then three shuffle levels, grid table (256 words) in work-group
memory; `:60-75` `xxs_pair_packed` adds gate+up and the SiLU product. `research/decode-next2/RESULT.md` ~40-67:
1,074 -> 730 us per token over 18 sites, bit-exact (SG16 only ~945). `research/decode-experts/RESULT.md`: packed
lanes won for IQ4_NL down 60.6 -> 37.6 us, Q2_0 56.9 -> 28.9, IQ4_XS 105.7 -> 52.0; they **lost** for IQ3_XXS
(61-93 vs 57) and IQ3_S / IQ2_S (57-64 / 44-51 vs 35.4 / 32.3) against `MultiplyBlockRows<4>`
(`packet6-kopt/kernels.cpp:462-521`: lane owns 8 consecutive columns, decode8, R = 4 rows share an 8-column x chunk,
adjacent-pair tree). Reading: packed lanes beat one-weight-per-lane forms and lose to a form that already decodes
8 consecutive weights per lane. **Our kernels are the one-weight-per-lane kind.** `MultiplyBlockRows` itself is
not usable as-is (its column ownership l*8 + 256i changes our sums), but 8 logical lanes per item gives the same
memory pattern with our order.

The 8-lane form for our order: item t of a group of 4 owns logical lanes 8t..8t+7 = columns 32c + 8t + j, i.e.
exactly one 8-weight grid entry per chunk (IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS pairs / IQ1_S groups are 8-aligned),
so per 8 weights: one index read, one or two table reads (two `d32x4` reads of a float table, or one 64-bit read
of the 2 KB byte grid as Vulkan does), one sign byte (the packer already expands signs, `pack_v41.hpp`), shared
scale; then per weight only `db * mag`, the sign xor, `* x`, `+`. Each logical lane keeps its own accumulator,
added chunk by chunk in ascending order, so every per-lane sum is unchanged. The end replays the xor butterfly
exactly: level 16 (lane ^ 16 = item t ^ 2) and level 8 (t ^ 1) are cross-item shuffles of the 8 registers; levels
4, 2, 1 are in-register adds (only those feeding lane 0: 4 + 2 + 1). This is exact because IEEE add commutes, so
every lane of a butterfly ends with the same bits and lane 0's value is all we store. 8 rows per sub-group (4 items
per row); 4-lane form: 4 rows per sub-group, levels 16, 8, 4 cross-item. Rows per expert: 384 (gate/up) and 864
(card 2 down) divide by 8; other cards' down slices need a masked tail.

Predicted instructions per weight (my estimate, to be replaced by the census): IQ2_XXS ~7.6 -> ~5-5.5,
IQ2_S ~12.2 -> ~5.5-6, IQ3_XXS ~12.9 -> ~6, IQ2_XS ~12 -> ~6, IQ1_S ~13 -> ~6. The floor is about 3 float ops
(mul, mul, add: the reference order fixes them) + 1 int (sign) per weight. If time follows instruction issue:
gate+up ~1.82 ms -> ~1.0-1.2, down ~1.04 -> ~0.6 on card 2. Also helps the register-dependency stalls (one wide
table read per 4-8 weights instead of one per weight) and gives 4-8 independent accumulator chains per item.

Exactness details to keep (all from the current kernels): sign as a sign-bit xor on `db * mag` (IEEE mul is
sign-symmetric, so `(db*mag)^s == db*(+-mag)`); decoded IQ magnitudes are exact in f32; IQ grid bytes are >= 1, so
the packed-byte negation `(g ^ m) + (m & 0x01010101)` (llama.cpp vecdotq.hpp:1515-1530, 1586-1587) never carries
if an int8-table form is tried.

Proof: (1) write `RoutedIQ2XXSK<4|8>` next to `RoutedIQ2XXSR` in `tools/bench/bench_routed_m1.cpp` (it already
compares an R-rows candidate bitwise against production at the six-card shapes: pair 384 rows x 20 blocks, down
864 x 9); (2) `tools/perf/dump_isa.sh` + `isa_census.py --loops` on it, no GPU: keep only if int ops per chunk
drop by ~2x and no spills (large-GRF mode allowed); (3) one-card time on any card, bitwise on every output; then
IQ2_S and IQ1_S (the two slowest per weight), then IQ3_XXS / IQ2_XS down; (4) `test_routed_u` for the multi-token
expert-major path if the forms are shared. Caveat from §23: R rows per lane (x shared across rows) was slower
here (R=2 33.2 vs 32.1 us); packed lanes are a different shape (more columns per item, one row per item), but the
same "lane-group broadcast becomes an indirect move" trap applies: check the census for `move.indirect`.

### L3. Stamp-in-data exchange (one trip)

oneCCL's LL protocol on this card family: `/home/steve/src/oneccl-public-qwen27/deps/libccl/src/coll/algorithms/utils/protocol/
proto_rt64_128.hpp:23-47` (15 of 16 lanes payload, the 16th a flag, uncached cache controls), flags inserted at
`:133-192`, receiver polls the data itself at `:447-501`. On this host in the two-card era the oneCCL all-gather
added 4.8 us after a matmul for 1 x 5120 fp16 and 6.4 us for 6 x 5120 (`experiments/qwen38-27b-b70/notes/
2026-10-17-fp8-step-floor.md:330-360`; alone 15.2 us). DeepSeek-REAP TP4 notes: `experiments/deepseek-v4-flash-
reap-xpu-b70/notes/2026-07-14-tp4-collective-protocol-pivot.md:30-50` (Rt64_128_PCIE, no peer atomics).

For our pull: the producer writes its slice into its own arena with a sequence stamp per 16-byte (or 8-byte) unit;
the receiver loads data and stamps together and reloads only units whose stamp is old. When the producer is
already done this is one load round trip instead of flag + load (save ~2.5-3 us of ~12 per pull, 83 pulls).
Safety: only rely on the access size that is single-copy atomic over PCIe; the 8-byte (4 data + 4 stamp) form is
the safe one, halves payload, and our slices are 3.4-9.5 KB per card so latency dominates. Proof:
`xchg_lat_bench` variant (it already splits full / nofence / nocopy / copy), then `xchg_pull_test` with changing
data, 2,000 iterations, 0 wrong.

### L4. MoE launch diet

Today per layer: gate+up (one launch for all 6 experts and both matrices, already like OpenVINO's mlp_gate_up),
SwigluBothS (applies `prob[r] * silu(min(g, lim)) * clamp(u)`, :4567-4585), activation pull, down,
MoeCombineA (`shared + sum_r exps`, :1161-1170), h push. OpenVINO does SwiGLU in the gate+up epilogue and the
routing weight in the down epilogue (3 launches per MoE: `mlp_gate_up`, `mlp_down`, `mlp_reduce`, extracted
blob `0046_mlp_gate_up.cl` :356-511, :623); Vulkan fuses ADD_ID and the router-weight MUL into the mat-vec
epilogue (`ggml-vulkan.cpp:14630-14645`, `mul_mat_vec_base.glsl:107-121`). Their arithmetic is fp16 / FMA, the
structure is usable.

Our gate and up rows of one index run in different sub-groups (`OWN41_ROUTED_ROWS_BEGIN`: w2 rows after all w rows),
so a gate+up epilogue needs either both rows in one sub-group (§23: 2 rows per sub-group cost ~3 %, more than the
launch saves) or a last-finisher counter (SC117: xtail-style tails were slower and unsafe, DO-NOT-REPEAT). The
cheap exact form: do the card's own SwiGLU slice in the activation exchange launch before it publishes, and the
expert sum of the card's own h rows in the h push launch before it stores. Same expressions, same floats. Saves
~80 launches per word, roughly 80 x (1.1-1.5 us kernel tail + ~1 us gap) ~0.1-0.2 ms. SC117 F1 (gate+up+SiLU in
one launch, 87.7 -> 65.6 us, `research/tp/fixed-cost-2026-10-30/RESULT.md`) shows the launch saving is real on
B70. Proof: 3-step trace byte-identical to `runs/ab1/base.trc`, b1 profile.

### L5. XchgPull index math

`copy_seq` (sycl_v41.hpp:5816+) indexes with `size_t` (k, n4, k % n4, base % T) and reads `b0[d]` / `b1[d]` with a
runtime d. B70 emulates 64-bit integer divide / modulo (research/2026-10-25-decode-roofline.md:25-60: removing
64-bit math and 64-bit-to-float took IQ2_S 80.1 -> 33.5 us), and runtime-indexed private arrays become indirect
moves (§23). The copy is ~5-6 us of round trip, so this is a sub-microsecond cleanup; check the census first and
only touch it together with L3.

### Prompt reading (P1-P3)

- Decode once per block into shared memory, then every token of the block multiplies the f32 weights from there
  (Vulkan `mul_mm_funcs.glsl:115-150` decodes tiles to shared memory; usable in f32 with our order: the decode is
  exact, the per-token sums keep the one-token order). Removes per-weight-token decode moves (§31 d2: shift, three
  moves byte -> word -> float, an indirect move for the scale).
- Reuse tiles: SC117 `research/prefill-reuse/RESULT.md` (reuse2 tiles, dense 3.52 -> 1.10 ms per row, 1.34x end to
  end, exact) and `research/prefill-experts/RESULT.md` (expert-grouped, 3.21 -> 1.29 ms per row, 1.48x).
- Transpose reduction when one sub-group finishes 32 outputs: `packet194-expert-diet-engine/prefill_reuse2.hpp:180-218`, 31 shuffles per 32
  outputs instead of 5 per output. Exact only if the halving order equals the target tree: bit 0 first reproduces
  `sg_tree32` (adjacent pairs, dense kernels), bit 4 first reproduces the routed xor butterfly.
- llama.cpp's default prompt path dequantizes to f32 and calls oneDNN / oneMKL sgemm (ggml-sycl.cpp:3265-3267,
  3370-3400; GGML_SYCL_F16 off, common.hpp:102-114): f32 but the library's summation order, so idea only.

## What each source has

### llama.cpp SYCL (`ggml/src/ggml-sycl/`)
- IQ types at batch 1 go to Q8_1 activations and dp4a (`ggml-sycl.cpp:4456-4475, 5286-5293`; MoE `mmvq.cpp:2630-2707`,
  one launch over (1, n_used, nrows) with ids read on the GPU): **not usable** (activation quantization).
- ESIMD f32 mat-vec for Q2_K..Q6_K (`esimd.hpp:76-590`) and Q8_0 (`dmmv.cpp:1747-1869`); no IQ types. Lane j owns
  column j of each 32-chunk in ascending order (like ours), but super-blocks are split over 4 threads (Q8_0: stripes
  of 8 blocks over 1-8 threads, :1852-1869) and the thread totals are added serially after a tree: different order.
  Built with icpx's default -fp-model=fast (no fp-model in the SYCL CMakeLists; `ggml/src/CMakeLists.txt:220-224`),
  so `acc += y * w` very likely becomes FMA: **not usable as an order**. Usable idea: SoA Q8_0 (all qs, then all d,
  :1795) with block loads of 256 activations per stripe; we already pack quads + scales.
  Hand counts (helper, not measured): Q8_0 ~3 ops per weight, Q4_K ~4, Q5_K ~7, Q6_K ~6-7.
- XMX part of esimd.hpp (:590-1399): int8 DPAS with Q8_1 activations: **not usable**. GLU-fused ESIMD
  (`dmmv.cpp:1574-1608, 1881-1925`): approximate exp2 sigmoid: **not usable**.
- Fusions (`ggml-sycl.cpp:6695-6800`, `fusion.cpp:8-85`): topk_moe (softmax / sigmoid only, power-of-2 experts:
  DeepSeek's sqrt(softplus) routing stays ~9 launches), rms_norm+mul(+add), add+add, gate+up+GLU (never for
  MUL_MAT_ID). DeepSeek V4 hyper-connections `dsv4-hc.cpp:15-198` are one plain kernel each; lightning indexer one
  kernel, 4 rows per block; sparse FA off by default and order-free (`fattn-sparse.cpp:28`: **not usable**).
  Helper's hand estimate of llama.cpp's DeepSeek V4.1 decode: 60-90 launches per layer (`src/models/deepseek41.cpp:
  409-917`), ~17 more on compression tokens. We run ~26.
- SYCL graph (`ggml-sycl.cpp:6907-7080`): off unless `GGML_SYCL_ENABLE_GRAPH=1`, and `check_graph_compatibility`
  turns it off when more than one device is active, or when MUL_MAT_ID / FA need a host sync. Nothing to copy for
  six cards. Our own measurement agrees: a SYCL graph of 1,142 launches 19.86 vs direct 19.82 ms
  (`stage2/packet34-replay-bench/receipts-card3-20261012-r1/README.md`, under own-xpu-runtime, not engine/src); in our b1 profile kernel time already
  equals wall time.

### llama.cpp Vulkan (`ggml/src/ggml-vulkan/vulkan-shaders/`)
- f32 IQ mat-vec shaders: `mul_mat_vec_iq2_xxs.comp:10-46` (64-bit grid entry in shared memory read as
  `iq2xxs_grid[qs].x / .y`, 7 sign bits by `bitfieldExtract` + parity by `bitCount`, 8 weights per item), iq2_xs
  `:10-63`, iq2_s `:10-48`, iq3_xxs `:10-46`, iq1_s `:10-53`; grid tables `types.glsl:985-991`, shared-memory init
  `:1081-1090`. The order is **not usable** (nested FMA over 8 weights, then `fma(db, sum8, acc)`: scale after
  sum). The decode form (8 weights from one 64-bit table read, signs from one byte) is the model for L2's 8-lane
  form. Helper's hand estimate ~5.5-6 instructions per weight.
- Rows per work-group for Intel: `ggml-vulkan.cpp:2883-2910`. MoE: one dispatch per token with ADD_ID and the router
  MUL fused into the epilogue (`:14630-14645`, `mul_mat_vec_base.glsl:107-121`), a sqrt-softplus routing pattern
  (`:14764`). Command buffers submitted per ~100 nodes. Interface file is `mul_mat_vec_iface.glsl:8-28`.

### OpenVINO GenAI 2026.4.1 GPU plugin
Plugin `/mnt/fast-ai/builds/ov-genai-repro/venv/lib/python3.12/site-packages/openvino/libs/libopenvino_intel_gpu_plugin.so`;
no source checkout on disk, OpenCL (not Level Zero), no command-buffer replay seen. Kernel sources are embedded as
strings: extract with `strings -n 8 <plugin.so>` and split at kernel boundaries; the blob names below are from my
session scratch extraction (`cl/` = newer embedded kernels, `k/` = kernel_selector templates), so re-extract to
cite exact lines. The models used for the lab numbers were deleted.
- `fully_connected_gpu_gemv` (k/g203): SG16, 16 sub-groups split K by scale groups (`thread_task_splitter`
  :59-71), partials in SLM [16][16] and a final reduce (:286-300), fp16 math: **not usable** (split K, fp16).
- int4 layouts `os_iyx_osv16` / `osv32_isv2` (k/g138 :41-92): idea only.
- `moe_3gemm_swiglu_opt` (cl/0046): `mlp_gate_up` :356-511 reads expert pointers from an on-device expert list
  (:395-408), splits the activation even / odd into SLM (:440-452), a row pair per sub-group, SiLU x up in the
  epilogue, the shared expert as an extra slot; `mlp_down` puts the routing weight in its epilogue (:623);
  `mlp_reduce` sums in fp16. Structure usable (L4), arithmetic not.
- `sigmoid_bias_topk` (cl/0050 :60-109): rank counting, the same idea as our branch-free router pick (rp3).
- Graph passes: FullyConnectedHorizontalFusion, SwiGluFusionWithClamp, RMSFusion, RoPEFusion.
- Lab numbers: OV 114.7 tok/s vs llama.cpp 99.5 on Qwen2.5-7B INT4 (~480 GB/s,
  `community/bosd-openvino-genai-b70/validation/lab-run.md`). Its first greedy generation differs from later ones
  (memory `openvino-genai-b70-lane`), so nothing about its order is reproducible anyway.

### Our older engines (SC117 / Qwen own runtime / FP8 lanes)
- Packed logical lanes: L2 above.
- Direct stores, shared native context, EnableDeferBacking=0: L1 above.
- Kernel boundary 0.63 us empty / 0.64-1.1 us; grid barrier 0.57 us + ~10 ns per group; HC chain 37.45 us separate
  vs 41.04 persistent; 65,536 resident items max (`research/persistent-layer-2026-10-30/RESULT.md`): the barrier
  megakernel is a no-go, which pc1 confirmed for our dense chain.
- Fixed-cost study (`research/tp/fixed-cost-2026-10-30/RESULT.md`): F1 gate+up+SiLU one launch 87.7 -> 65.6 us;
  F2 deferred event retirement -0.3 ms per half, +7.3 % end to end on four cards. Our host is already ahead of the
  cards (kernel time = wall time), so F2 is only worth it if a profile shows host-side gaps.
- Lean-loop rules (`research/2026-10-25-decode-roofline.md:25-60`): 32-bit indices, no 64-bit-to-float, no
  runtime-indexed private arrays. Our routed kernels mostly follow them; `OWN41_ROUTED_ROWS_BEGIN` does a 64-bit
  divide per row only when rider rows exist (:1832-1833), XchgPull does not (L5).
- Expert diet (packet193): 15.28 -> 11.81 instructions per weight with `isa_count.py`, the same census method as
  `tools/perf/isa_census.py`.
- Quad overlap (repo-root `docs/sc117-engine-review.md:98-110`) is a scheduling of four owner pipelines, not a kernel
  technique; nothing to port.
- ESIMD rewrites in other lanes lost (`experiments/qwen27_fused_postattn_rms_w4a16/README.md` 74-95).
- Dense reads: research/dense-raw 454-588 GB/s (`packet194-expert-diet-engine/p33_dense_raw.hpp:23-84`) and the REAP lane's 579 GB/s with 16-byte
  loads; our dense Q8_0 GEMVs are at ~475-495 GB/s and the Q6_K head at ~569, so dense is near its floor.

## Not usable (do not port)

| Technique | Where | Why |
|---|---|---|
| Q8_1 activations + dp4a / int8 DPAS | llama.cpp SYCL mmvq, esimd.hpp XMX, Vulkan mmvq / mmq | activation quantization |
| fp16 / bf16 math, fp16 reductions | OpenVINO gemv and MoE (mlp_reduce), Vulkan mul_mm f16 | lower precision |
| DPAS / coopmat / oneDNN / joint_matrix | llama.cpp fused-gemm.cpp, XMX paths | rounding matrix units, library order |
| Scale after the 8- or 32-weight sum | Vulkan IQ (`fma(db, sum8, ...)`), OpenVINO group scales | reordered sum |
| Split K across sub-groups or threads | OpenVINO gemv, llama.cpp ESIMD (4 threads, serial add) | reordered sum |
| FMA chains / -fp-model=fast | llama.cpp ESIMD and Vulkan | contraction changes rounding |
| Q5_K min folded into a sum, IQ1_S delta via sum(x) * delta | llama.cpp vecdotq / Vulkan | reordered sum |
| Approximate exp / sigmoid (ESIMD exp2, native_exp, powr) | llama.cpp GLU-fused ESIMD | approximation |
| Order-free sparse attention | llama.cpp fattn-sparse.cpp:28 | output order not fixed |

## Already tried here or in SC117 (do not repeat without a new reason)

- R rows per sub-group sharing x (§23: R=2 33.2 vs 32.1 us, R=4 45 us); 96 work-groups for the pair (§24, closed);
  uneven TP row shares (balance only inside a stretch between exchanges, §24 lines 870-875).
- Barrier megakernel (SC117 persistent-layer, pc1 2026-11-11). SYCL graph replay (packet34: no gain).
- `XchgPull::copy_lb` (slower, e81d). Pushes for big slices (1 GB/s here).
- SC117 DO-NOT-REPEAT (`gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md`): IQ3_XXS FMA / lane-contiguous / rows / grid in
  the load module lost; xtail last-work-group tails unsafe and slower; HC fusion gave time back; merged small GEMVs
  slowed the next big kernel; rebalancing gave nothing.
- IQ3_XXS sign expansion in the packer (7 % slower, kept unexpanded).

## Suggested order

1. L1 probe (host RAM, then `xchg_bw_bench` shared-native mode): one short run decides the largest item.
2. L2 census for IQ2_S and IQ2_XXS 8-lane forms (offline, can run beside anything), then `bench_routed_m1` on one
   card; IQ1_S next.
3. L3 only if L1 says peer stores stay slow; L5 rides with it.
4. L4 in the next batch gate (cheap, exact by construction).
