# Decode next 2 (rank 1): HC BF16 GEMVs and IQ3_XXS / IQ3_S / IQ2_S gate+up, exact (2026-10-26)

**Engine.** Canonical `engine/src` is the live service engine ef3a2665ffe5 (canonical + decode-next). The reference
binary is `/dev/shm/engine-build-svc-b16-dnext-20261026/sc117-engine`.

**Lab.**
- `/dev/shm/ownrt-lab-dn2/engine` is the variant tree: canonical, the lab-only profiling deferral
  (`research/decode-experts/profile-defer-lab.patch`), and every variant below.
- `/dev/shm/ownrt-lab-dn2/clean/engine` is canonical + `decode-next2.patch` + the profiling deferral. The final binary
  was built from it with a full, non-incremental build.

**Runs.**
- Rank 1 alone on card 27, through `tp_rank1_driver.py` engine-path runs only, under `flock /dev/shm/card27.lock`.
- Each run held only renderD131.
- Launch: the live unit's environment plus `OWNRT_DECODE_NEXT=1`, `--target-split 23`, context 65536, `--rows 256`.
- Fault checks:
  - before each run, the kernel log for any xe fault since the lab started;
  - after each run, the kernel log for that run's window.
  - Every check was clean.
- No device microbenchmarks were run. Every new kernel body was first tested bitwise on the OpenCL CPU device with
  GPU access blocked (`cputest/`, `nodri.so`), including under DeviceSanitizer, on real model rows.

## Result

**Best exact configuration: `OWNRT_DECODE_NEXT2=1`** (xxs + hcgate + bf16split; default off).

Final interleaved sequence (`runs/F-*`) used the final binary
`/dev/shm/engine-build-lab-dn2-final/sc117-engine` (d2bc8008eb8d), built in full from canonical +
`decode-next2.patch` + the profiling deferral. The reference was the live engine b16 (ef3a2665ffe5).

| Prompt | Reference (driver median ms, rank-1 half) | `OWNRT_DECODE_NEXT2=1` | Change |
|---|---|---|---:|
| 4096 rows | 12.958 / 12.957 / 12.961 | 12.578 / 12.585 / 12.592 | **−0.374 ms (−2.9%)** |
| 4096 rows, half_completion median | 12.906 / 12.904 / 12.911 | 12.524 / 12.535 / 12.532 | −0.377 ms |
| 300 rows | 12.815 | 12.426 | −0.389 ms |
| 4096 rows, final binary with the switch off | 12.977 | | default off is inert |

- Bitwise: every final run matches its reference in all 1079 state buffers (differ_count 0, nothing on one side, no
  other field differs), and the generated tokens are identical.
- Kernel log: 0 fault lines. Every run held only renderD131.
- Profile span per half: 12598 → 12225 µs (−374 µs), which matches the end-to-end change.
- **Effect on the two-card service.** Rank 0 was not measured here. The coordinator's per-position split was rank 0
  about 12.08 ms (11.42 half + 0.66 draft wait) and rank 1 about 11.68 ms. The xxs, hcgate and bf16split sites run on
  rank 0's layers as well:
  - HC and router sites run on every layer;
  - the IQ3_XXS block sites on rank 0 are blk.0/7/12/14/16/18/20/22, i.e. 8 of the 17 selected layers.
  - Rank 0 should therefore drop by a similar amount, and it is now the side that sets the pace.

## What changed (`decode-next2.patch`, switch `OWNRT_DECODE_NEXT2`, default off; "1" = xxs, hcgate, bf16split)

**xxs: routed IQ3_XXS gate/up at the 18 block sites** (`dn2_kernels.hpp`, `block.hpp`).
- This is `iq3block::BlockRowsOperation<4>` with packed logical lanes.
  - Original mapping: lane l of a row owns column `256*block + 32*group + l`. Each lane decodes one element per
    group, which costs one grid gather, one sign and scale word, and one input load per element.
  - New mapping: in a 32-lane subgroup, set = lane/8 takes one row, so there are still 4 rows per subgroup and 8
    work-items per row (the same item count). Item t owns logical lanes 4t..4t+3.
- Per group, the four lanes share three things:
  - the index byte `b[2+8*group+t]`; one grid word holds their four magnitude bytes;
  - the sign code, since lane/8 = t/2;
  - the factor `(d*(0.5f+float(word>>28)))*0.5f`, computed once with the same operations.
- Each lane's value is still `(factor*float(mag))*float(sign)`. Its product and add keep the original block/group
  order.
- Tree: `((l0+l1)+(l2+l3))` in registers (the first two adjacent-pair levels), then three shuffle levels.
- The 256-word grid is read from a work-group copy.
- Profile: 1074 → 730 µs per token. End to end: −0.34 ms per half.
- The 32-lane subgroup is essential. With 16-lane subgroups (two rows per subgroup) the kernel only reached about
  945 µs. With 32 lanes, four rows share each input load message.

**hcgate: HC gate GEMVs (BF16, 10240 × 320, K ≤ 1024).** `dense_v2::bf16_multi<2,4>` instead of `<4,4>`: 2 rows
per subgroup, the same per-row arithmetic. Profile: 843 → about 820 µs. End to end: −0.03 ms.

**bf16split: dense BF16 rows with 1024 < K < 8192** (router + shared gate, GDN a+b, QSA iq+ik).
- `dense_v2::bf16_split<10,4>`: a row's 32 logical lanes go to two 16-lane subgroups of one work-group, with the same
  chunks per lane and the same load-then-add order.
- Tree: levels 1–8 use the same xor butterfly (lower + upper at every node). The last level, `node(0..15) +
  node(16..31)`, goes through work-group memory.
- Profile: router 201 → about 191 µs, GDN a+b 75 → about 59 µs. End to end: −0.02 ms.
- HC low (K 10240) keeps `bf16_multi<1,8>`, because the split was neutral or slower there.

## Final per-site profile (rank 1, 4096-row prompt; `profile-final.json` vs `profile-reference.json`)

Floor @600 is µs per token at 600 GB/s. The reference column is the canonical engine; the final column is
`OWNRT_DECODE_NEXT2=1`.

| Site | Launches | Reference µs | Final µs | Change | MB per token | Floor @600 | Final % of 600 floor |
|---|---:|---:|---:|---:|---:|---:|---:|
| `routed_gemv:IQ3_XXS:expsgate` | 9 | 549.0 | 374.2 | −174.8 | 56.4 | 94 | 25% (was 17%) |
| `routed_gemv:IQ3_XXS:expsup` | 9 | 524.8 | 346.6 | −178.2 | 56.4 | 94 | 27% (was 18%) |
| `gemv:BF16:hc.a.gate` | 25 | 407.9 | 400.8 | −7.1 | 163.8 | 273 | 68% |
| `gemv:BF16:hc.f.gate` | 25 | 435.4 | 426.5 | −8.9 | 163.8 | 273 | 64% |
| `gemv:BF16:hc.a.low` | 25 | 400.2 | 404.5 | +4.3 (unchanged kernel) | 163.8 | 273 | 68% |
| `gemv:BF16:hc.f.low` | 25 | 430.7 | 437.5 | +6.8 (unchanged kernel) | 163.8 | 273 | 62% |
| `gemv:BF16:router` (+ shared gate) | 25 | 200.8 | 194.4 | −6.4 | 65.5 | 109 | 56% |
| `gemv:BF16:gdn.a` (+ gdn.b) | 18 | 74.7 | 61.5 | −13.3 | 4.4 | 7 | 12% |
| `routed_gemv:IQ3_S:expsgate` / `expsup` | 8 + 8 | 293.2 / 278.0 | unchanged | | 56.3 each | 94 | 32–34% |
| `routed_gemv:IQ2_S:expsgate` / `expsup` | 7 + 7 | 229.4 / 213.9 | unchanged | | 36.7 each | 61 | 27–29% |
| span per half | | 12598 | 12225 | −374 | 3055.5 | | |

## Profile screens (µs per rank-1 token, `OWNRT_DECODE_PROFILE=3`, 4096-row prompt; `screens.json`)

Sites: XXS g/u = IQ3_XXS expsgate/expsup; S g/u = IQ3_S expsgate/expsup; S2 g/u = IQ2_S expsgate/expsup.

| Run | Variants | XXS g | XXS u | S g | S u | S2 g | S2 u | hc.a.low | hc.f.low | hc.a.gate | hc.f.gate | router | gdn.a | span |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| a0-prof | reference | 549 | 525 | 293 | 278 | 229 | 214 | 400 | 431 | 408 | 435 | 201 | 75 | 12598 |
| p1 | xxs packed SG16 / global grid; S+S2 block rows, SLM grid; hclow split U8; hcgate packed | 485 | 465 | 288 | 269 | 252 | 217 | 444 | 465 | 472 | 489 | 206 | 78 | 12699 |
| p2 | xxs packed SG16 / SLM grid; split U10 for every K>1024; hcgate R2 | 485 | 458 | – | – | – | – | 404 | 429 | 401 | 425 | 188 | 57 | 12416 |
| p3 | xxs original mapping / SLM grid; hclow split U4; hcgate R8 | 523 | 493 | – | – | – | – | 422 | 450 | 417 | 441 | 196 | 66 | 12598 |
| q1 | xxs packed SG32 / global grid; S+S2 packed SG16; hclow lazy U20; hcgate R2 | 396 | 374 | 366 | 346 | 284 | 261 | 402 | 433 | 396 | 422 | 194 | 61 | 12506 |
| q2 | **xxs packed SG32 / SLM grid**; S+S2 packed SG32; hclow lazy U40 GRF256; hcgate R2 | **377** | **353** | 351 | 340 | 283 | 273 | 411 | 442 | 400 | 423 | 206 | 78 | 12645 |
| q3 | S+S2 packed SG16 / SLM; hclow lazy U20 GRF256; hcgate packed | 486 | 466 | 371 | 339 | 388 | 329 | 393 | 429 | 471 | 494 | 204 | 78 | 13136 |
| q4 | S+S2 packed SG32 / SLM; hclow lazy U40; hcgate packed | 485 | 458 | 338 | 320 | 314 | 283 | 403 | 430 | 477 | 496 | 204 | 78 | 12861 |
| pq1 | xxs SG32/SLM as one gate+up launch; S block rows SLM grid; S2 32-bit codebook halves; hclow lazy U20 | 807 (both) | – | 286 | 269 | 228 | 214 | 397 | 429 | 401 | 422 | 194 | 60 | 12404 |

## Interleaved end-to-end A/B (driver median ms of the rank-1 half, 4096-row prompt, two runs each)

Every run is bitwise identical to the reference: differ_count 0 of 1079 state buffers.

| Round | Arm | Run 1 | Run 2 | Verdict |
|---|---|---:|---:|---|
| e1 | ref (b16, ef3a2665ffe5) | 12.996 | 12.973 | |
| e1 | xxs SG32 / SLM grid | 12.661 | 12.618 | **−0.34** |
| e1 | xxs SG32 / global grid | 12.659 | 12.674 | −0.32 |
| e1 | xxs + hcgate R2 + bf16split | 12.607 | 12.604 | **−0.38** |
| e2 | ref | 12.959 | 12.983 | |
| e2 | B = xxs + hcgate + bf16split | 12.618 | 12.606 | −0.36 |
| e2 | B + xxspair (gate+up one launch) | 12.668 | 12.683 | +0.06 vs B, negative |
| e2 | B + IQ3_S SLM grid + IQ2_S 32-bit codebook | 12.602 | 12.594 | −0.01 vs B, noise |
| e2 | B + HC low lazy U20 GRF256 | 12.739 | 12.739 | +0.13 vs B, negative |
| e3 | B | 12.596 | 12.600 | |
| e3 | B without hcgate | 12.635 | 12.629 | hcgate is worth −0.03 |
| e3 | B without bf16split | 12.622 | 12.619 | bf16split is worth −0.02 |
| e3 | B + IQ3_S SLM grid only | 12.594 | 12.600 | 0.00, dropped |

## Exactness

`tp_rank1_driver.py compare` checked all 1079 state buffers after the decode steps, with no buffers ignored:

| Comparison | Compared | differ_count | Only on one side | Other fields |
|---|---:|---:|---:|---|
| F-ref-1 vs F-new-1 (4096) | 1079 | 0 | 0 | none |
| F-ref-2 vs F-new-2 | 1079 | 0 | 0 | none |
| F-ref-3 vs F-new-3 | 1079 | 0 | 0 | none |
| F-ref-p300 vs F-new-p300 (300 rows) | 1079 | 0 | 0 | none |
| F-ref-1 vs F-off-1 (switch off) | 1079 | 0 | 0 | none |
| a0-prof vs F-prof (profile mode) | 1079 | 0 | 0 | none |

- The generated tokens are identical in every pair.
- Every screen and A/B arm above, negatives included, was also differ_count 0. All variants were exact; they were
  dropped only for speed.
- CPU device (OpenCL CPU, GPU blocked; plain and DeviceSanitizer):
  - `xxs_packed<4>` matches a verbatim replica of `BlockRowsOperation<4>` on real blk.30 gate and up rows, including
    an invalid route, a short row_count and the status words;
  - `bf16_multi<2,4>` matches `<4,4>` (HC gate blk.30, synthetic 2051×96);
  - `bf16_split<10,4>` matches `bf16_multi<1,8>` (router + shared gate, GDN a+b, synthetic K 2600 pairs).
  - Sentinel tails showed no out-of-range stores.

## What did not work, and why

**HC low (320 + 4 rows × K 10240, about 400–430 µs per token, 2 × 25 launches).** None of these helped:
- splitting a row's 32 logical lanes over two 16-lane subgroups (U = 4/8/10 chunks per step: +20 to +44 / 0 µs);
- loading 20 or 40 chunks before use with weights only, inputs at use (128 or 256 registers): −7 to +11 µs in the
  profile, and +0.13 ms end to end for U20 GRF256.

Each logical lane is a serial chain of 40 chunk adds. Having more weight bytes in flight did not shorten the kernel.
Its time behaves like a fixed per-launch cost: about 5–6 µs over the 10.9 µs floor, the same excess as every 6.5 MB
GEMV here. That cost can only come down with fewer launches, but these GEMVs have a full dependency between them.

**HC gate (10240 × 320).**
- Packed logical lanes (8 items per row in 16-lane subgroups): +55 to +65 µs.
- 8 rows per subgroup: +6 to +9 µs.
- 2 rows per subgroup is the only gain, and it was kept.

**IQ3_S / IQ2_S gate/up.**
- Packed logical lanes (16- or 32-lane subgroups, global or SLM grid): +40 to +160 µs. The kopt
  `MultiplyBlockRows<4>` mapping already needs only 0.25 grid reads per element and shares each input chunk across
  four rows; packing gives up that sharing.
- A work-group grid copy: IQ3_S −15 µs, IQ2_S +25 µs.
- IQ2_S codebook as two 32-bit halves (no 64-bit shifts): 0.
- End to end, both levers are within noise.

**IQ3_XXS gate+up as one launch (xxspair).** Same per-row work and item count, half the launches. Profile 807 vs
730 µs; end to end +0.06 ms. Not kept.

The code for every variant is in `neg/lab-all-variants.patch`: hclow U4/8/10/20/40 and GRF, hcgate packed/R2/R8, xxs
modes 1–5, S variants 1–6 and xxspair. The same switches select it.

## Files

- `decode-next2.patch`: the final change against canonical `engine/src`. It was verified to reproduce the clean tree
  with `profile-defer-lab.patch`. It touches:
  - `packet194-expert-diet-engine/decode_next2.hpp` (new): switches;
  - `packet194-expert-diet-engine/dn2_kernels.hpp` (new): the standalone XXS body, also compiled by the CPU tests;
  - `expert-iq3xxs-block/.../block.hpp`: `XxsDn2Operation` and its hook;
  - `packet6-kopt/dense_v2.hpp`: `bf16_split`;
  - `packet6-kopt/kernels.cpp`: the hcgate and bf16split hooks.
- `cputest/`:
  - `test_final.cpp` (the final headers) with `test_final.out` and `test_final_asan.out`: PASS;
  - `test_dn2.cpp`: every lab variant; all PASS.
- `scripts/`: run, launch maker, medians, profile tools.
- `profile-reference.json` (a0-prof), `profile-final.json` (F-prof), `screens.json` and `results.json`.
