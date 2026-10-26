# Prefill dense GEMV weight reuse ("reuse2"), 2026-10-26

**Verdict: win, and exact.** Behind `OWNRT_PREFILL_REUSE2=1` (default off), rank 1 alone on card 27 reads a 4096-row
prompt in 32-row chunks in **31.0 / 31.4 s, against 41.9 / 42.0 s** for the unmodified build. That is 1.34x end to end,
or about 1.40x after removing the driver's ~4.5 s of Python stream generation.

The dense GEMV share drops from **3.52 to 1.10 ms per row (3.2x)** in the per-site profile. All 13 timed and profiled
reuse2 runs, including every sweep configuration, are bitwise identical to the unmodified batched reference: all 1079
state buffers match and the tokens are equal. The partial last chunk (4090 rows) is also identical.

- Patch against `engine/src`: [prefill-reuse.patch](prefill-reuse.patch). It touches 4 files and adds 2 headers; a
  dry-run apply to the current canonical tree is clean.
- Run identities: [results.json](results.json).
- Compact evidence per run (summary, state.json, profile, run log, kernel-fault grep): [evidence/runs/](evidence/runs/).

## What it is
- **One tile kernel for all dense formats.** `reuse2::Tile<Format,RW,T,S,GRF,O>` is a 32-lane subgroup that owns RW
  weight rows x T token rows of register accumulators. Per 256-column step, each lane decodes its 8 values of each row
  once, using the format's own expression, and applies them to all T tokens.
  - Formats: dense packed blocks Q4_K/Q5_K/IQ4_XS (`block_element`, stride-32 lanes); p33 expanded Q6_K/Q8_0
    (`scale*float(int8)`, 8-column lane chunks); kopt raw Q6_K/Q8_0 (`kopt::decode8`); raw BF16 (bits<<16).
- **Exactness.** Every output keeps its single-row sequence: steps ascending, the 8 values of a step ascending, product
  first, then `sum = sum + product`.
  - The reduction is the same adjacent-pair tree, computed as a **butterfly transpose**: lanes exchange halves of their
    accumulator list with `permute_group_by_xor`. Each addition is still (lower-lane partial) + (upper-lane partial)
    over the same lane ranges.
  - This needs 31 shuffles per 32 outputs instead of 160, and the outputs leave in one store instead of 32 single-lane
    stores.
- **Index math is 32-bit.** Only the per-subgroup row and token bases are 64-bit. Stride-32 activations use subgroup
  block reads.
  - Large-GRF mode comes from the `grf_size<256>` kernel property (compiler 2026.0), per kernel.
- **Dispatch and switches.**
  - Hooks: `denseblock::issue` (block.hpp), `p33::dense_issue`, and `kopt::gemv_tokens`.
  - Per-family tile switches: `OWNRT_PREFILL_REUSE2_{BLOCK,P33,KOPT,BF16}=i`. The value `5` selects the canonical kernel.
  - Defaults are per shape class: dense blocks 2x16 with row tiles adjacent; p33 4x8; kopt 1x32 up to 1024 rows,
    otherwise 2x16; BF16 1x1 up to 64 rows, 1x4 up to 128 rows, the canonical lean kernel for k >= 8192, otherwise 4x8.
- **Diagnostics.**
  - `OWNRT_PREFILL_REUSE2_CYCLE=1` cycles tile i = chunk % (count+1), canonical included. One profiled run therefore
    times every tile side by side, and the final state still gates them all.
  - `OWNRT_PREFILL_PROFILE_SHAPE=1` keys the profile by rows x columns.
- **No other changes.** Nothing changes with the switch off (r2g-off: identical state, 41.98 s). Decode (tokens == 1)
  is untouched.

## Pre-device gates (CPU only)
- **Bitwise equality on the OpenCL CPU device.** [evidence/cputest/test_reuse2.cpp](evidence/cputest/test_reuse2.cpp)
  runs every tile config on the CPU device, isolated with an LD_PRELOAD guard that blocks /dev/dri. It compares
  against host replicas of the original per-lane loops.
  - Coverage: 12 format/shape cases (k = 320 .. 10240, 37 rows, 13 and 32 tokens).
  - Every config passed (288 + 72 + 120 cases), including clamping and partial tiles. This also guards against
    out-of-bounds indexing before any device launch.
- **Spill check.** An AOT `bmg-g31` compile reports spills.
  - The production tiles do not spill. The exploratory 4x16 tiles spill 8-15 registers.

## Measurements (rank 1, card 27, 32-row chunks, warm JIT cache)

### End to end
| run | build | prompt_ms (4096 rows) | state vs reference |
|---|---|---|---|
| ref-t32 / ref-t32b | unmodified `0df557b3` | 41852 / 41982 | identical |
| r2g-off-t32 | final `e259812d`, switch off | 41983 | identical |
| **r2g-t32 / r2g-t32b** | **final `e259812d`, REUSE2=1** | **30959 / 31387** | **identical** |
| r2d-t64 | 64-row chunks | 30921 | identical (no gain over 32) |
| r2g-p4090 vs ref-p4090 | 4090 rows (partial chunk) | 31142 vs 41725 | identical |

### Per-site profile (ms per row, r2g-off-prof32 vs r2g-prof32)
The profile mode drains after every site, so it includes about 20 µs of sync per call.

| site | off | on |
|---|---|---|
| dense Q6_K | 0.860 | 0.240 |
| dense BF16 | 0.731 | 0.392 |
| dense Q5_K | 0.697 | 0.127 |
| dense Q8_0 | 0.683 | 0.210 |
| dense Q4_K | 0.309 | 0.059 |
| dense IQ4_XS | 0.244 | 0.067 |
| **dense total** | **3.524** | **1.096** |
| routed experts | 3.39 | 3.30 |
| qsa_attention | 1.05 | 1.03 |
| gdn | 0.62 | 0.61 |

#### Per shape (ms per chunk, off -> on)
- **Q5_K** 10240x2560: 12.97 -> 2.26.
- **Q8_0** 2560x6144: 16.86 -> 4.98.
- **Q6_K**
  - 10240x2560: 9.35 -> 2.38
  - 12288x2560: 6.87 -> 1.71
  - 6144x2560: 5.69 -> 1.45
- **Q4_K** 6144x2560: 5.62 -> 0.93.
- **BF16**
  - hc up, 10240x320: 14.11 -> 5.02.
  - inject, 4x10240: 2.57 -> 1.23.
  - hc down, 320x10240: stays on the canonical kernel, 3.55.

## Tried and closed
- **Lane-0 tree epilogue (r2b).** Gave a 2.0x dense gain, but hc up (k = 320) only went 14.1 -> 12.3 ms per chunk. The
  butterfly epilogue (r2c) took it to 5.0 and lifted every shape.
- **Half-split 128-GRF tiles (r2f).** Two 4-value halves per step, for twice the occupancy. Slower everywhere, for
  example Q8_0 2560x6144 8.2 vs 5.2 ms per chunk and hc up 21 vs 5. Removed.
- **Tiles that never won a site class.** 2x8, 1x16, 4x16 (spills), 2x4, 8x4, 2x16 with token tiles adjacent (the
  row-tile-major 2x16 won narrowly), and 4x8 with row tiles adjacent. They are kept only under `-DREUSE2_EXPLORE`, so
  production JIT builds 5 tiles per format.
- **BF16 320x10240 (hc down).** Every tile lost to the canonical lean 2x4 kernel (3.82 best vs 3.57), from low
  parallelism and activation re-reads. It stays canonical.
- **64-row chunks.** 30.92 vs 31.03 s, which is noise. Card memory did not change (owned_bytes 31871276652).

## Notes
- **JIT cost.** On a cold cache, the first prefill JITs the new kernels: about 15 s for the 5-tile list, about 30 s for
  the 15-tile sweep build. It is cached afterwards in `SYCL_CACHE_DIR`. The very first reference run on a cold cache took
  71 s for the same reason.
- **Card hygiene.** Every launch held only renderD131. `journalctl -k` showed no xe fault, reset or GuC lines after any
  run.
- **Next levers on this rank.**
  - Routed experts are now the largest share at 3.3 ms per row. The same tile kernel could serve experts once slots
    are grouped by expert.
  - Then qsa_attention (1.0 ms per row at 4K context) and gdn (0.6).
  - The remaining dense time is about 1.1 ms per row. The large matrices run at about 2.5-3 TMAC/s with separate
    mul/add.
