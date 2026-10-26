# Dense decode GEMVs: roofline and exact faster kernels (2026-10-26)

SC117 Qwen3.8 Flash-Next IQ3_S, own engine, F32 activations, rank 1 alone on card 27, split 24, context 65536.
Every run used the service env (`OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1 OWNRT_PREFILL_REUSE2=1
OWNRT_SELECT_TOPK=1 OWNRT_SELECT_FAST=1 OWNRT_RESET_DEVICE_ZERO=1`). Lab only; canonical tree untouched.

**Status: stopped early on a GPU fault (see Incident).** The work below is measured and exact. The final
interleaved timing series, the 300- and 30000-row gates, and the M=2 verify check were not run.

## Result

`OWNRT_DENSE_DECODE_V2=1` (default off). Patch: `dense-decode.patch` against canonical `engine/src`:
- 4 edited files: `stage2/packet6-kopt/kernels.cpp`, `.../dense-packed-block/.../block.hpp`,
  `.../additive/packed.hpp`, `stage2/packet194-expert-diet-engine/p33_submit.cpp`;
- 3 new headers: `stage2/packet6-kopt/dense_v2.hpp`, `.../additive/dense_decode_v2.hpp`,
  `stage2/packet194-expert-diet-engine/p33_dense_v2.hpp`.

**Rank-1 half at a 4096-row prompt (single runs, median of 48 halves):**

| build | half (ms) |
|---|---|
| reference `1655bcde...` | 16.543 |
| c1: BF16 only | 15.860 |
| c2: + packed-block | 15.095 |
| c3: + p33 Q8_0, the patch | 15.106 |

That is about −1.44 ms (−8.7%).
- The rank-1 device profile span went from 15782 to 14638 µs; GEMV device time fell 1006 µs per half.
- State compare against the reference: differ_count 0 and identical tokens for c1, c2 and c3 (1032 buffers).

## What changed (all exact: same per-output operation sequence)

1. **kopt `Multiply`, dense BF16 rows** (hc.*.low + inject fused pairs, hc.*.gate, final.*, qsa.iq, gdn.a, router).
   - Lane l keeps the reference chunks (8l + 256i), the serial `acc = acc + w*x` from 0.f, and the adjacent-pair tree.
   - New: no SLM/work-group barrier (raw rows were never staged), and a uniform subgroup index.
   - Loads: U = 8 chunks of loads ahead of their in-order arithmetic for long rows; for k ≤ 1024 with ≥ 2048
     rows, R = 4 rows per subgroup with the R trees reduced by a transposing butterfly (lower + upper).
   - Fused sibling launches (up to 4 descriptors) are supported.
2. **Packed-block Q4_K/Q5_K/IQ4_XS rows** (`DenseBlockOperation` and the dense `PackedOperation` decode: gdn.qkv,
   gdn.z, shexp gate/up, qsa.qgate Q5_K).
   - Same per-lane element order (k = 32j + l) and field equations
     (factor = d·float(scale), offset = dmin·float(min), weight = factor·float(code) − offset;
     IQ4_XS through `iq4_level`, the same integers as the local table, which lowered to private memory).
   - One 16-byte (8-byte for IQ4_XS) header load per block, code bytes per group pair.
   - Subgroup-uniform row index, so the per-group scale arithmetic is scalar. This was the main gain.
   - 4 rows per subgroup for the 4096–8192-row z projections.
3. **p33 expanded Q8_0, 6144 columns** (attention output): 2 rows per subgroup, 2 tiles of loads ahead, same
   tile/scale/`value*x` sequence; −2.2 µs per call in-engine.

Prefill row kernels (DenseBlockRows, reuse2, gemv_tokens paths), routed experts and the generic `specialised` body
are untouched. The hooks only fire for tokens = 1, dense (no routes), F32 in/out.

## Roofline (rank 1, per call, 600 GB/s = measured random-data stream read on card 27)

Weights read per call: p33 sites read expanded storage, i.e. int8 codes plus an F32 scale per 16 (Q6_K) or 32 (Q8_0)
columns.

| site | kernel | shape | calls | MB | floor µs | before µs (%) | after µs (%) |
|---|---|---|---|---|---|---|---|
| logits Q6_K | p33 | 2560→248320, expanded (raw 521 MB) | 1 | 794.6 | 1324 | 1378 (96) | 1376 (96) |
| attention Q8_0 | p33 | 6144→2560, expanded | 24 | 17.7 | 29.5 | 40.9 (72) | 38.3 (77) |
| gdn.qkv Q6_K | p33 | 2560→10240, expanded | 8 | 32.8 | 54.6 | 71.0 (77) | 69.7 (78) |
| hc.f.low BF16 | kopt (+inject) | 10240→320 | 24 | 6.55 | 10.9 | 22.4 (49) | 18.0 (61) |
| hc.a.gate BF16 | kopt | 320→10240 | 24 | 6.55 | 10.9 | 22.0 (50) | 17.1 (64) |
| hc.f.gate BF16 | kopt | 320→10240 | 24 | 6.55 | 10.9 | 21.9 (50) | 16.4 (66) |
| hc.a.low BF16 | kopt (+inject) | 10240→320 | 24 | 6.55 | 10.9 | 21.1 (52) | 16.2 (67) |
| gdn.qkv Q5_K | denseblock | 2560→10240 | 7 | 18.0 | 30.0 | 66.5 (45) | 50.2 (60) |
| qsa.qgate Q6_K | p33 | 2560→12288, expanded | 5 | 39.3 | 65.5 | 83.3 (79) | 81.9 (80) |
| shexpdown Q8_0 | kopt staged | 640→2560 | 24 | 1.74 | 2.9 | 15.1 (19) | 15.0 (19) |
| gdn.z Q6_K | p33 | 2560→6144, expanded | 8 | 19.7 | 32.8 | 41.7 (79) | 40.9 (80) |
| router BF16 | kopt? | 2560→512 | 24 | 2.62 | 4.4 | 8.5 (52) | 7.8 (56) |
| gdn.z Q4_K | denseblock | 2560→6144 | 5 | 8.85 | 14.7 | 36.0 (41) | 25.0 (59) |
| gdn.qkv IQ4_XS | denseblock | 2560→10240 | 2 | 13.9 | 23.2 | 67.6 (34) | 53.9 (43) |
| gdn.a BF16 | kopt | 2560→96 | 18 | 0.49 | 0.8 | 6.7 | 4.2 |
| gdn.z Q5_K | denseblock | 2560→6144 | 3 | 10.8 | 18.0 | 39.5 (46) | 29.3 (62) |
| shexpup / shexpgate Q6_K | kopt staged | 2560→640 | 8 / 7 | 1.34 | 2.2 | 11.7 / 12.5 | 11.6 / 12.6 |
| gdn.z IQ4_XS | denseblock | 2560→6144 | 2 | 8.36 | 13.9 | 41.0 (34) | 31.3 (45) |
| shexp gate/up Q4_K, IQ4_XS, Q5_K | denseblock | 2560→640 | 33 | 0.87–1.13 | 1.5–1.9 | 8.7–10.8 | 6.4–7.3 |
| qsa.qgate Q5_K | gsqn/denseblock | 2560→12288 | 1 | 21.6 | 36.0 | 78.6 (46) | 59.3 (61) |
| qsa.k / qsa.v Q6_K | kopt staged | 2560→512 | 6 / 6 | 1.08 | 1.8 | 11.5 / 9.8 | 11.4 / 9.6 |
| qsa.iq BF16 | kopt | 2560→512 | 6 | 2.62 | 4.4 | 10.4 | 8.9 |
| Q4_K gdn.qkv | denseblock | 2560→10240 | 1 | 14.8 | 24.6 | 59.5 | 44.8 |
| final.gate / final.low BF16 | kopt | | 1 / 1 | 6.55 | 10.9 | 22.1 / 19.6 | 16.8 / 15.2 |

Full numbers per site: `results.json` `roofline_table`.

### Findings
- **Logits are at 96% of the roofline for their storage.** p33 stores Q6_K/Q8_0 expanded: 1.25 B/element for Q6_K
  (vs 0.82 raw), 1.125 for Q8_0. The logits head, qkv/z/qgate Q6_K and attention are bound by those bytes
  (77–96%).
  - Decoding raw Q6_K/Q8_0 blocks on the fly gives identical values: the expansion is
    scale = half(d)·float(sc), value = scale·float(q), the same F32 operations.
  - That would cut the logits floor to ~870 µs (−0.45 ms) and the Q6_K sites by ~35%.
  - Not done: the prefill agent's reuse2 kernels read the same expanded buffers, and the cards cannot hold both
    copies. It needs a joint decision (raw storage plus raw-decoding prefill tiles).
- **The packed-block decode was instruction-bound** because the row index was not provably subgroup-uniform. Making
  it uniform scalarised the per-group scale arithmetic: −25 to −33%.
- **Small GEMVs (≤ 2.6 MB: shexp*, qsa.k/v, router, gdn.a) run at 15–25% of the roofline.** They are latency /
  launch bound.

### Tried and closed (bench, exact unless noted)
- kopt quantized rows (Q8_0/Q6_K) decoded straight from global memory instead of SLM staging: up to 2× slower (byte
  loads).
- Packed-block R = 2/4/8 rows with `block_element` unchanged: slower (private-memory table, spills).
- BF16 prefetch-ahead variants (L1/L2, distance 8–16): no gain over U = 8.
- p33 v2 for Q6_K shapes: at the expanded roofline already, no gain cold.

## Incident (stopped all device work)

At **08:50:29** card 27 logged "Fault response: Unsuccessful -ENOENT" (ASID 3358, address 0x0000d556aa2a0000, bcs,
FaultLevel 4) and "Engine reset: engine_class=bcs, guc_id=6". sc117-lan halted itself at 08:50:33, as designed.

- **Context:** my microbenchmark `bench_quant` (a new staged-quantized variant) aborted twice with
  UR_RESULT_ERROR_OUT_OF_RESOURCES. One bench-only variant requested 209 KB of local memory. The process exited
  abruptly with work in flight.
- The second abort coincided with the fault lines, in the same second that the decode-experts agent's engine
  (pid 294276) started loading on card 27.
- My process's abrupt exit is a likely cause (an abrupt-exit fault pattern is known on this host); the other start
  is a possible one.
- No engine run of mine was active. I stopped all device work, did not retry, and took no recovery action (no
  service restart).
- That kernel variant (`quant_rows_staged`) is **not** in the patch. It is kept untested in
  `bench/kernels.with_quant_staged_untested.cpp`; its engine hook had a 64 KB local-memory guard, the bench did not.

## Not verified (because of the stop)
- Final interleaved A/B timing series (only single runs above).
- 300- and 30000-row prompt gates.
- Two-row (M=2 verify) decode: the hooks require tokens = 1, so token rows use the existing kernels. Unverified.

## Next steps (decode tok/s)
1. Gate `OWNRT_DENSE_DECODE_V2=1` (this patch) with the interleaved series and the 300/30K gates, then ship
   (≈ −1.4 ms per rank-1 half at 4K).
2. Joint decision with the prefill agent: keep Q6_K/Q8_0 dense weights raw (smaller VRAM) and decode raw blocks in
   both paths. That is ≈ −0.45 ms on logits plus ≈ −0.3 ms on Q6_K sites per half, exact by construction.
3. Small GEMVs: fuse or batch the 2.6 MB-and-smaller sites per layer (latency bound, 15–25% of the roofline).
4. Staged quantized rows (shexpdown, shexp Q6_K, qsa.k/v; ~0.75 ms of device time): retry `quant_rows_staged`
   only after the incident review, with the bench launch-size bug fixed.
