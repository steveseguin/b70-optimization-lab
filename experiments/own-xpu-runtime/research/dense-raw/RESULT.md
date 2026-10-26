# Raw-size storage for the p33 dense Q6_K / Q8_0 weights (`OWNRT_DENSE_RAW=1`), 2026-10-26

SC117 Qwen3.8 Flash-Next IQ3_S, own engine, GSQ path, F32 activations and F32 KV. Rank 1 alone on card 27, split 24,
context 65536, the live service environment (`OWNRT_EXPERTS_V2`, `OWNRT_DENSE_DECODE_V2`, `OWNRT_PREFILL_EXPERTS`,
reuse2, attention heads, select top-k/fast, ...), 256-row prefill chunks. Lab copy only; the canonical tree is untouched.

**Verdict: win, exact, ready to gate in the service.** Rank 1's decode half drops by 0.95 ms (−6.8%), and rank 1
frees 611 MB of VRAM (rank 0: 278 MB). Every device run is bitwise identical to the unmodified build.

The freed VRAM does **not** make the 23/25 split fit at 64K by itself. Rank 1 at split 23 would still exceed the
30 GiB plan cap by 145 MB, and by 362 MB at runtime with the 218 MB of 256-row prefill shadows. See "Owned bytes".

## Result

| rank 1, 4096-row prompt, 256-row chunks | reference `5e44953236cc` (live service) | `OWNRT_DENSE_RAW=1`, final `4fbd350831e3` | change |
|---|---|---|---|
| decode half, driver median of 48 (3 interleaved runs) | 13.849 / 13.921 / 13.875 → **13.875 ms** | 12.946 / 12.926 / 12.919 → **12.926 ms** | **−0.949 ms (−6.8%)** |
| decode half, 300-row prompt | 13.727 ms | 12.777 ms | −0.950 ms |
| device span per half (`OWNRT_DECODE_PROFILE=2`) | 13,470 µs | 12,565 µs | −905 µs |
| prompt time, 4096 rows (median of 3) | 16,851 ms | 16,958 ms | +107 ms (+0.6%) |
| prompt time, 300 rows | 1,283 ms | 1,291 ms | +8 ms |
| load (ready) | 11.5 s | 14.4 s (12.4 s with `OWNRT_DENSE_RAW_VERIFY=0`) | +2.9 s |
| rank 1 VRAM, runtime census, split 24 | 31,789,014,212 B | 31,177,563,332 B | **−611,450,880 B** |

- **Exactness.** Runs were compared against the reference with `tp_rank1_driver compare`:
  - all 1032 state buffers equal (differ_count 0) and equal tokens, in every compared run;
  - compared runs: the 3 timing runs, the warm-up, the 300-row pair, the 30,000-row pair, the switch-off run, the
    prefill tile-cycle pair, all 10 kernel-configuration runs (c3/c4) and the first c1 runs.
  - Four early profile runs (c1/c2) were checked on tokens only.
  - Across all 31 device runs, the generated tokens are identical for each prompt length (4096, 300 and 30,000).
- **Card hygiene.**
  - Every engine run held only `/dev/dri/renderD131`.
  - `journalctl -k` showed no fault, reset, hang or timeout line before or after any run. The last such line on the host
    is still the 08:50:29 incident.
  - No standalone device microbenchmark was run. Kernel analysis was CPU-only: AOT `bmg-g31` ISA dumps and the OpenCL
    CPU device with `/dev/dri` blocked.

## Affected tensors and bytes

GSQ mode stores exactly these tensors expanded: the logits head, plus every weight of the p33 policies (attention Q8_0,
QKV Q6_K and dense Q6_K). Everything else is already raw (gsqn, kopt, dense blocks, IQ3 blocks). Prefill reads the same
buffers. The 90 tensors:

| class | shape (rows x cols) | expanded row | raw row | count (rank 0 / rank 1 at split 24) | saved per tensor |
|---|---|---|---|---|---|
| logits head Q6_K | 248320 x 2560 | 3380 B | 2100 B | 0 / 1 | 317,849,600 B |
| gdn.qkv Q6_K | 10240 x 2560 | 3380 | 2100 | 14 / 8 | 13,107,200 |
| gdn.z Q6_K | 6144 x 2560 | 3380 | 2100 | 6 / 8 | 7,864,320 |
| qsa.qgate Q6_K | 12288 x 2560 | 3380 | 2100 | 0 / 5 | 15,728,640 |
| attention output Q8_0 | 2560 x 6144 | 7296 | 6528 | 24 / 24 | 1,966,080 |

- Rank 1 at split 24: 46 tensors, 1,938,278,400 → 1,326,827,520 B (−611,450,880 B), from the engine's own
  `dense-raw.json`.
- Rank 0 at split 24: 44 tensors, −277,872,640 B.
- At split 23, layer 23's attention output (Q8_0) moves to rank 1: rank 1 then saves 613,416,960 B and rank 0
  275,906,560 B.
- The rank-0 draft keeps its own expanded head prefix, 91392 rows with BF16 activations, unchanged. It never shared the
  target head (that lives on rank 1). With the switch on, a raw target head is never shared (`mtp.hpp` guard).

## Owned bytes, split 23 and 24 (cap 30 GiB = 32,212,254,720 B)

Plan figures are `write_plan`'s `owned_bytes`. They were taken with a lab-only `OWNRT_PLAN_ONLY=1` stop
(`plan-only.patch`) that exits before device contact; the split-23 reference runs are refused by the plan cap anyway.
Runtime figures are census device totals; rank 1's runtime is the plan plus 217.93 MB of 256-row prefill shadows.

| | split 24, reference | split 24, raw | split 23, reference | split 23, raw |
|---|---|---|---|---|
| rank 1 plan | 31,571,082,372 | 30,959,631,492 | 32,970,184,300 (over by 757.9 MB, refused) | 32,356,767,340 (over by 144.5 MB, refused) |
| rank 1 runtime (256-row chunks) | 31,789,014,212 (measured) | 31,177,563,332 (measured; 1,034.7 MB headroom) | ≈33,188 MB | ≈32,574,699,180 (over by 362.4 MB) |
| rank 0 plan (target, without draft) | 28,001,334,316 | 27,723,461,676 | 26,602,232,388 | 26,326,325,828 |
| rank 0 runtime (≈ plan + 3,702,809,406 draft and shadows, from the live census) | 31,704,143,722 (live) | ≈31,426,271,082 | ≈30,305,041,794 | ≈30,029,135,234 |

- **Split 23 at 64K needs 145 MB more off rank 1's plan**, and 362 MB at runtime with 256-row chunks.
- Smaller chunks alone do not close it. The plan is over before any shadows: 128-row chunks still leave 254 MB over,
  32-row chunks 172 MB.
- What is left on rank 1 at split 24 (raw):
  - weights 29.00 GB;
  - F32 KV 1.86 GB (6 QSA layers × 311 MB at 64K);
  - prefill shadows 0.22 GB;
  - recurrent state 0.06 GB;
  - workspace 0.04 GB.

  At split 23, layer 23 adds 1.086 GB of weights and 311 MB of KV.

## Exactness proof

**Values.**
- The expanded loader stores, per element:
  - the code int8(q) (Q6_K: q = code6 − 32);
  - one F32 scale word S: S = half(d)·float(int8 sc) for Q6_K, an exact product (s1_lanes.hpp), or S = half(d) for Q8_0.
- The expanded kernels form value = S·float(q).
- The raw decoders form the same real product with exact steps:
  - **Q6_K:** value = s4·float(int8(q<<2)), with s4 = (half(d)·0.25f)·float(sc).
    - half(d)·2⁻² and the product with sc are exact, because |half(d)| ≥ 2⁻²⁴ (or 0) is far above the F32 subnormal
      range and the product has at most 19 significant bits.
    - So s4 = S/4 exactly, and s4·(4q) rounds the same real number S·q. Signed zeros match.
  - **Q8_0:** value = half(d)·float(int8 code).
- iq3::half is the loader's conversion on the host. On the device the decoders use the hardware conversion for every
  non-NaN half, selected (not branched) against iq3::half's canonical quiet NaN.

**CPU proof, every element of every affected tensor** (`cputest/prove_dense_raw.cpp`, `evidence/cpu/prove_dense_raw.out`).
It reads the 90 tensors from the GGUF and, for 2,344,878,080 elements, gets 0 mismatches in each check:
1. The raw decode (the kernels' code, host-compiled), through both the per-block path (prefill tiles) and the per-pair
   path (decode kernels), equals scale·float(int8 code) of the engine's `iq3::expanded::expand` rows, as bits.
2. It also equals `iq3::expanded::value` (the engine's CPU reference) for every element.
3. Un-repacking (an independent inverse) gives the GGUF bytes back (raw = a permutation of the GGUF bytes).
4. The p183 census passes: no non-finite d, and every scale word equals the metadata product.
5. d classes: 6,178,482 of 29,803,520 blocks have a subnormal fp16 d (20.7%) and 60 a zero d. So the device's
   subnormal half conversion is exercised by every gate.

**Load-time proof (default on).** With `OWNRT_DENSE_RAW_VERIFY` unset, the loader decodes every uploaded raw element and
compares it bitwise with the expanded row that the default build uploads. Rank 1 checks 1,506,017,280 elements with 0
mismatches; a mismatch refuses the start. This costs about 2.0 s per rank-1 load.

**CPU-device kernel test** (`cputest/test_raw_kernels.cpp`, `evidence/cpu/test_raw_kernels.out`).
- Setup: OpenCL CPU device with GPU access blocked by `nodri.so`; real head and attention rows (first and last 37 rows).
- Coverage: every decode configuration (R 1/2/4/8, U 1/2/4) and every production reuse2 tile at 1/3/13/32 tokens.
- Result: all 132 cases are bitwise equal to a host replica of `Kernel<0,T,K,1,true>`, and none stores out of range.

**Device gates.**
- Full state (1032 buffers) and tokens are bitwise equal to the unmodified build in every run listed above.
- That includes 4096-row prompts in 256-row chunks (16 chunks) and a 300-row prompt (a partial 44-row chunk).

### 30K gate
- Setup: a 30,000-row prompt in 256-row chunks (118 chunks, the last of 48 rows) plus 48 decode steps, final binary
  `4fbd350831e3`.
- Result: full state and tokens bitwise equal to the reference.
- Timing: half 13.904 → 12.960 ms (−0.944 ms); prompt 124.7 → 125.7 s (+0.8%).

## What changed (`dense-raw.patch`: 9 files under `engine/src`, 2 new headers)

### Layout
`dense_raw.hpp` defines the layout: the GGUF bytes, rearranged so that a lane's columns are aligned word loads.

**Q6_K row (K % 512 = 0):** four planes per block pair (blocks 2p and 2p+1, 420 B), the same 210 B per block.

| plane | offset | contents |
|---|---|---|
| L | 0 | per lane, two u32 (one per block) with the 8 low nibbles |
| H | K/2 | per lane, two u16 with the 8 high-2-bit fields, XOR 2: the top of q's 6-bit two's complement |
| S | 3K/4 | the 16 int8 sub-scales of both blocks, interleaved |
| D | 13K/16 | both fp16 d |

- Decoding assembles (q<<2) as signed bytes with word-parallel masks.
- One pair costs a lane four loads: 8 B of L, 4 B of H, 2 B of S, and a uniform 4-byte d.

**Q8_0 row:** the int8 codes as they are, then the fp16 d plane.

### Loader (`main.cpp`)
- Under `OWNRT_DENSE_RAW=1` (GSQ, F32 activations, resident only), the head and the p33 policy weights are uploaded
  raw. The expanded rows are still built on the host for the p183 census and the per-element check.
- `Matrix::raw` (`kopt2::Matrix`, default false) marks these matrices.
- The p28/p33/policy extent checks and `write_plan` (stored bytes, `"layout":"raw"`) use the raw sizes.
- `dense-raw.json` records per-tensor bytes and the proof counters.

### Kernels (`p33_dense_raw.hpp`, `p33_submit.cpp`)
All F32-in / F32-out and exact:
- **Decode rows.** Each output keeps `dense_lane`'s per-lane order: tiles ascending, 8 columns, product then
  `sum = sum + product`.
  - The 32-lane adjacent-pair tree is reduced by v2's transposing butterfly.
  - Measured defaults: Q6_K 1 row × 1 block pair (configuration `111`), Q8_0 1 row × 2 tiles of loads ahead (`121`),
    128 GRF.
  - `OWNRT_DENSE_RAW_Q6=RUG` and `OWNRT_DENSE_RAW_Q8=RUG` select another configuration: 111, 121, 141, 211, 221, 411,
    412 or 811, with R rows, U pairs or tiles ahead, and G=2 for 256 GRF.
  - Token rows without reuse2 use the same kernel.
- **Prefill.** Prefill uses the reuse2 tiles with a raw format (`Reuse2Raw<T>`). The tile switch and defaults are
  unchanged (`OWNRT_PREFILL_REUSE2_P33`, default 4x8).
- **No other path changed.** M=2 verify runs serial single rows through the same decode kernels. Every other path is
  unchanged, and with the switch off nothing changes.

## Per-site device time (rank 1, µs per half, `OWNRT_DECODE_PROFILE=2` with the lab profiling deferral, 48 halves)

The roofline is 600 GB/s over the bytes each layout reads. Expanded rows read codes plus scale words; raw rows read all
of their bytes.

| site | calls | expanded µs/call (% roofline) | raw µs/call (% roofline) | per half |
|---|---|---|---|---|
| logits Q6_K 248320x2560 | 1 | 1375.5 (96%) | **886.9 (98%)** | −488.6 |
| gdn.qkv Q6_K 10240x2560 | 8 | 69.56 (79%) | 47.17 (76%) | −179.1 |
| qsa.qgate Q6_K 12288x2560 | 5 | 81.58 (80%) | 55.66 (77%) | −129.6 |
| gdn.z Q6_K 6144x2560 | 8 | 40.88 (80%) | 27.94 (77%) | −103.5 |
| attention Q8_0 2560x6144 | 24 | 38.23 (77%, DENSE_DECODE_V2) | 36.81 (76%) | −34.1 |
| **dense raw sites** | | 3584.6 | 2649.7 | **−934.9** |

Unchanged sites moved by +8 to +19 µs: gdn, hc.f.gate, hc_combine. The net span change is −905 µs.

**Prefill, profiled tile cycle** (ms per call at 256 rows, best tile 4x8 for both layouts):

| site | expanded | raw |
|---|---|---|
| Q6_K 10240x2560 | 2.170 | 2.484 |
| Q6_K 12288x2560 | 2.513 | 2.888 |
| Q6_K 6144x2560 | 1.319 | 1.501 |
| Q8_0 2560x6144 | 1.191 | 1.231 |

- The in-register unpack costs about 14% on the Q6_K token tiles. That is the +0.6% prompt time, about 6.8 ms per
  256-row chunk on rank 1.
- No raw tile beats 4x8. The 2x16 row-major tile is about equal.

## Relation to the closed packed-format rows
packet74 (packed Q6_K/Q8_0 dense and head: −0.8 to −2.9%), packet93 (block-transposed head: lane-A loss) and
packet183 S1 (metadata scales: −6.2%) closed in-register unpacking on the old BF16 kernels. Their DO-NOT-REPEAT row
reads "unless a new mechanism removes the unpack cost". Three things changed here:
- subgroup-uniform block-pair loads (8 + 4 + 2 bytes per lane, a uniform d);
- a word-parallel unpack into (q<<2) signed bytes, with the scale pre-divided by 4 (exact);
- spill-free 1-row kernels, with x loaded at its use. The first raw layout spilled and only reached 1120 µs on the head.

The head now reads its raw bytes at 98% of the 600 GB/s roofline. That row should note this result as the exception.

## Tried and closed
- **v1 layout (blocks in order, per-lane u32 low / u16 high words, 4 rows x 2 tiles):** head 1120 µs, spilling, and
  Q8_0 attention 42 µs (a per-lane branch in the half conversion made the subgroup diverge). Replaced.
- **Kernel configurations.** Spills are from AOT `bmg-g31`; per-call times are in µs (`evidence/cpu/aot-bmg-g31-spills.txt`):

  | config | spill | logits | qkv | qgate | z | attention |
  |---|---|---|---|---|---|---|
  | R4 U1, x loaded ahead (c3) | 1.1 KB | 1025 | 58.9 | 66.1 | 34.4 | – |
  | R2 U1, x loaded ahead (c3) | none | 890 | 48.3 | 57.4 | 29.0 | – |
  | R4 U2 (AOT only) | 2.7 KB | – | – | – | – | – |
  | R2 U1 | none | 889 | 48.4 | 57.4 | 29.1 | – |
  | R4 U1 | none | 908 | 55.6 | 62.2 | 33.5 | – |
  | R4 U1 GRF256 | none | 891 | 49.7 | 59.1 | 30.5 | – |
  | R8 U1 | none | 1133 | 58.9 | 67.7 | 41.8 | – |
  | **R1 U1 (chosen)** | none | **887** | **47.2** | **55.7** | **28.0** | – |
  | R1 U2 | none | 890 | 49.0 | 57.5 | 29.4 | – |
  | R1 U4 | none | 892 | 51.5 | 60.0 | 32.2 | – |
  | Q8 R1 U2 (chosen) | none | – | – | – | – | **36.8** |
  | Q8 R1 U1 | none | – | – | – | – | 37.0 |
  | Q8 R1 U4 | none | – | – | – | – | 37.7 |
  | Q8 R2 U2 | none | – | – | – | – | 37.8 |
  | Q8 R2 U1 | none | – | – | – | – | 40.0 |
- **int16-lane layout** (natural bit order; float(int16) conversions): exact, and all 132 CPU-device cases pass. The AOT
  ISA has the same instruction count as the shipped layout (170 vs 171 for Q6_K R1U1), so it was not adopted. It was
  never run on the device.
- **Byte extraction through a `vec<int8_t,4>` bit-cast:** +10% instructions (byte, then word, then float moves). Shifts
  are kept.

## Service path: limits and files the lab driver bypasses
1. **`serving/lan/adapter6.py` `environments()`** passes only the OWNRT keys on its whitelist (line 57) to the ranks.
   - `OWNRT_DENSE_RAW` (and, if used, `OWNRT_DENSE_RAW_VERIFY`, `OWNRT_DENSE_RAW_Q6`, `OWNRT_DENSE_RAW_Q8`) must be
     added there and to `sc117-lan.service`.
   - Otherwise the service silently runs expanded. The lab driver takes the launch JSON's environment directly.
2. **Rank 0 never runs in this lab** (the driver drives rank 1 only).
   - Under the switch, rank 0 loads 44 raw tensors (24 attention, 14 qkv, 6 z) with the same kernels and shapes that
     were gated here.
   - The rank-0 draft and its expanded head prefix are unchanged.
   - Rank 0 is only covered by the service's own startup gates: the F32 state oracle at the context, and the one-time
     prefill gate. Its marker name contains every `OWNRT_*` variable, so the switch triggers a new gate run automatically.
3. **Native controller.** In the service, rank 0 drives rank 1 through the native mailbox
   (`native_controller.hpp`: request/reply sequence, abort, bounded waits). The lab driver replaces this with its own
   socket protocol, single halves and fixture 1 streams. Speculative halves and misses only run in the service.
4. **Prefill wire header.**
   - In the service, `adapter6.py` writes `prefill.bin`'s 16-byte header (magic `0x31465050`, version 1,
     `SC117_PREFILL_ROWS`, stream bytes), and `prefill_wire.hpp` reads it.
   - The lab driver writes its own header with `--rows`.
   - Unchanged by this patch, but the rows value must match the engine's `--prefill-rows`.
5. **Receipts and pins.**
   - `SC117_ENGINE_RECEIPT` pins the binary's receipt, so a new build needs a receipt and a unit change before any
     restart.
   - `adapter6.build_plan` refuses a build whose `root_binary_sha256` differs from the recorded one.
6. **Memory.**
   - With raw on, rank 1 has 1.03 GB of headroom at split 24 / 64K.
   - The unit's comment ("use 23 only with SC117_CONTEXT<=32768") still holds; see "Owned bytes".
   - Load time grows about 3 s per rank (repack plus proof); `OWNRT_DENSE_RAW_VERIFY=0` saves 2 s once trusted.

## Files
- **`dense-raw.patch`:** unified diff against canonical `engine/src`. Applied to a fresh copy, it reproduces the
  final lab source exactly; that source built `4fbd350831e3`.
- **`plan-only.patch`:** lab diagnostic `OWNRT_PLAN_ONLY=1`, not part of the switch.
- **`results.json`:** builds, every run (identity, timing, gates, bytes), the per-site tables and the owned-bytes table.
- **`cputest/`:** the GGUF directory reader, the affected-tensor list, the proof, the CPU-device kernel test, `nodri.c`
  and the AOT unit.
- **`evidence/`:** proof and test outputs, the AOT spill table, the affected-tensor TSV, and per-run summaries.
- Binaries:
  - final `/dev/shm/engine-build-lab-raw-c5/sc117-engine`;
  - profile and sweep build `/dev/shm/engine-build-lab-raw-c4/sc117-engine`.

  Runs are in `/dev/shm/ownrt-lab-raw/runs/`.

## Next steps (decode tok/s)
1. **Ship `OWNRT_DENSE_RAW=1` in the service.**
   - Add it to the adapter whitelist and the unit, build, write the receipt, and let the startup gates run.
   - Expected: rank 1 −0.95 ms per half, and rank 0 about −0.42 ms projected per position (14 qkv × −22.4 µs, 6 z ×
     −12.9, 24 attention × −1.4).
   - Rank 0 is the decode bottleneck, so its share is the one that moves tok/s.
2. **Raw draft head prefix on rank 0.**
   - Today 91392 rows × 3380 B = 309 MB are read per draft step, with BF16 activations.
   - A BF16-activation variant of the raw Q6_K kernel would save 117 MB on rank 0 and about 0.19 ms per draft step.
   - It needs a rank-0 gate path (the service's prefill gate, or a rank-0 driver).
3. **Split 23 at 64K** still needs 145 MB (plan) / 362 MB (runtime) off rank 1. Candidates:
   - move part of the head to rank 0 (only after rank 0's own gains);
   - plan the prefill shadows at the actual chunk rows;
   - review the per-layer `qsa.raw` and `pooled` KV buffers.
4. **Mid-size raw GEMVs** (qkv/qgate/z/attention) sit at 76–77% of the roofline, the same efficiency as before for
   fewer bytes. Their remaining loss is launch and tail (1–5 waves), not bytes.
5. **Prefill raw tiles:** win back the 14% Q6_K tile cost with a raw-specific tile that unpacks once per block pair
   (+0.6% prompt today).
