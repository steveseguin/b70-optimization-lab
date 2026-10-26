# Expert-grouped routed-expert prefill ("xgroup"), 2026-10-26

**Verdict: win, and exact.** Rank 1 runs alone on card 27, with context 65536, split 24 and the service environment
(reuse2, attention heads/combine2, select top-k).

| | 4096-row prompt | speedup |
|---|---|---|
| Service configuration (unmodified, 32-row chunks) | 26.65 / 26.75 s | baseline |
| **`OWNRT_PREFILL_EXPERTS=1`, `--prefill-rows 256` (final build x9 `dc76b4e9…`)** | **18.04 / 18.07 s** | **1.48x** (1.64x without the driver's ~4.5 s of Python stream generation) |
| `OWNRT_PREFILL_EXPERTS=1`, 128-row chunks (x6) | 19.25 / 19.24 s | 1.39x |
| `OWNRT_PREFILL_EXPERTS=1`, 80-row chunks (x5; no change to the native-kernel row limit) | 19.99 / 20.05 s | 1.33x |
| Final build with the switch off, 256-row chunks | 27.84 s | 0.96x |

- **Routed-expert share:** it falls from **3.21 to 1.29 ms per row (2.5x)** in the per-site profile at 256-row chunks
  (1.54 at 128 rows).
- **Exactness:** every grouped run (22, covering every sweep configuration at 32/64/80/128/256 rows, the timed runs and
  the partial-chunk runs) is bitwise identical to the unmodified batched run at 32-row chunks. That covers all 1032 state
  buffers and equal tokens. The unmodified kernels at 128 and 256 rows (switch off) are identical too.
- **Partial chunks:** the 4090-row runs, at 80 rows (last chunk 10 rows), 128 rows (last chunk 122 rows) and 256 rows
  (last chunk 250 rows), match the unmodified 4090-row run.
- **Card health:** every launch held only renderD131, and no fault lines followed any measured run. One card-27
  copy-engine fault was logged at the start of the final, optional exploratory run, x10. It is very probably not this
  work's; see "Fault". All device work stopped there.

Deliverables:
- Patch against `engine/src`: [prefill-experts.patch](prefill-experts.patch). It applies cleanly to the current
  canonical tree, including the newer select_fast change, and that tree compiles (not run).
- Run identities: [results.json](results.json).
- Per-run evidence: [evidence/runs/](evidence/runs/).

## What it is (`stage2/packet194-expert-diet-engine/prefill_experts.hpp`)
- **Bucket (one work-group, integer work only).** It runs per routed site and writes `status[s] = !valid(route)` exactly
  as the existing kernels do.
  - Slots with a valid full route are grouped by expert, in slot order, into tiles of at most T slots.
  - Any other slot (invalid or partial route) gets a tile of its own with its own route.
- **Tile kernel.** One subgroup owns RW rows of one expert, for the slots of one tile.
  - Each 256-column step decodes each lane's 8 values per row once, then applies them to every slot of the tile.
  - Decoding uses the exact function of the existing kernel for the site:
    - `iq3block::block_element_words` for the IQ3_XXS block sites;
    - `gsq::element_unchecked` for gsqn packed rows (IQ4_XS, Q2_0 and other GSQ types; Q2_0's dedicated loop computes
      the same `float(code-1)*d`);
    - `iq3::kopt::decode8<T>` for kopt routed rows (IQ2_S, IQ3_S, IQ4_NL, Q8_0, Q6_K).
- **Exact arithmetic.** Each (slot, row) output follows the existing lane mapping and order (stride-32 or 8-column
  chunks, including the ragged K=640 tails): product first, then `sum = sum + product`, then the same adjacent-pair
  tree (butterfly-transposed, from reuse2). Rows past `row_count` and invalid routes get the same quiet NaN.
- **Dispatch.** `prefill_experts_site` (in `prefill_engine.hpp`) mirrors `gsq_linear_matrix`'s site choice. Any site it
  does not recognise uses the existing path.
- **Scratch.** Slot order and tile descriptors take 61 KB at 256 rows.
- **QSA select in row groups (for chunks longer than its scratch allows).** The native qsa_select scratch holds
  rows x ceil(context/4) floats in the 8 MiB operator scratch, which is 128 rows at context 65536. Longer chunks run
  the native select in groups of at most that many rows, using `prefill_native_group`.
  - Each group runs from row g's views, as the grouped attention already does: the position/token views give row g
    its own position, and the shadows are viewed at row g.
  - Each group uses the extent its own last row admits, and every row keeps its single-row select.
  - Chunks within the limit are unchanged.

## Switches
| switch | effect |
|---|---|
| `OWNRT_PREFILL_EXPERTS=1` | Turns grouping on (default off). |
| `OWNRT_PREFILL_EXPERTS_{IQ3,ELEM,KOPT}=i` | Tile per family: 0 = 2x4, 1 = 1x4, 2 = existing kernel. Defaults are 1x4, except 2x4 for kopt IQ2_S/IQ3_S. |
| `OWNRT_PREFILL_EXPERTS_GDIV` | Launch divisor, default 4. |
| `OWNRT_PREFILL_EXPERTS_RLOOP` | Row tiles per subgroup, default 4. |
| `OWNRT_PREFILL_EXPERTS_CYCLE=1` | Diagnostic: cycles the tile per chunk, existing kernel included. |
| `OWNRT_PREFILL_ROUTE_DUMP=<file>` | Diagnostic: dumps the routes. |

### Chunk sizes
- **80 rows** need the 64-row limits raised: `--prefill-rows` cap, `gsqn::max_tokens`, `p28_max_tokens`,
  `kopt::gemv_tokens`. All are now 256.
- **Above 87 rows** also needs the native-kernel registered limit `ng::validate tokens <= 87` raised; it is now 256.
  - The first 128-row attempt was refused cleanly by that check (x2: "shape outside registered limits").
  - With the limit raised, the unmodified kernels at 128 and 256 rows are bitwise identical to the 32-row reference.
- **Above 128 rows at context 65536** needs the select row groups. Without them, 256 rows was refused cleanly by the
  binding guard (x8: "specialised scratch extent"). Every other native op's per-row scratch fits 256 rows (gdn 4.3 MB,
  route temporaries 4 MB).
- **Memory.** Rank 1's device memory against the 30 GiB arena admission:

  | chunk rows | owned | headroom | prefill shadows |
  |---|---|---|---|
  | 32 | 31.598 GB | 585 MB | 27 MB |
  | 128 | 31.680 GB | 508 MB | 109 MB |
  | 256 | 31.789 GB | 404 MB | 218 MB |

## Measurements
### Route statistics
From [evidence/launch/routestats.py](evidence/launch/routestats.py), rank 1, 24 layers, the driver's synthetic streams.
Routes are always full (row_begin 0), and down routes equal gate routes.

| chunk rows | slots | distinct experts | slots per expert | tiles per expert (T=4) |
|---|---|---|---|---|
| 32 | 320 | 188 | 1.71 | 1.05 |
| 64 | 640 | 278 | 2.30 | 1.14 |
| 80 | 800 | 308 | 2.60 | 1.19 |
| 128 | 1280 | 370 | 3.46 | – |
| 256 | 2560 | 440 | 5.82 | – |

Routing is skewed: the top 10 experts take 15% of a layer's routes.

### Routed ms per row: best tile vs existing kernel (profiled tile sweeps)
| chunk rows | grouped | existing |
|---|---|---|
| 32 | 2.30 | 3.20 |
| 64 | 1.91 | 3.17 |
| 80 | 1.73 | 3.19 |
| 128 | 1.57 | 3.21 |
| 256 | 1.29 (final defaults, x9-prof256) | – |

### Final per-type routed time at 128 rows (ms per chunk, existing -> grouped)
| site type | existing | grouped |
|---|---|---|
| IQ4_NL down | 159.0 | 65.4 |
| IQ3_XXS gate/up | 119.3 | 53.3 |
| IQ3_S | 58.6 | 37.8 |
| IQ2_S | 38.2 | 27.1 |
| IQ4_XS | 24.4 | 6.8 |
| Q2_0 down | 11.8 | 6.1 |

### Tile sweeps
- 2x4 and 1x4 win at every swept chunk size (32-128). The 256-row sweep was stopped at the fault, so 256 rows uses the
  128-row defaults.
- Losers: 4x2, 4x4, 4x8 and 8x4 (GRF 256), 2x8, 1x8, 1x16 and 1x2. RW=4 tiles of the gsqn formats are badly slow under
  JIT.
- Launch divisor 4-8 is best: 1.81 -> 1.75 ms per row. A row loop of 4 is neutral to slightly better.

## Gates
- **CPU-device bitwise test before any device launch:**
  [evidence/cputest/test_experts.cpp](evidence/cputest/test_experts.cpp).
  - Coverage: 6 formats x 7 tiles x 2 slot counts, with random routes including invalid and partial routes; also run
    with row loop 3 and divisor 5.
  - Result: 168/168 identical against host replicas of the existing per-lane loops and the existing status writes.
- **Device:** `tp_rank1_driver.py compare` against ref-4096 or ref-p4090.

## Fault
- **What was logged.** The x10-warm run was a 256-row tile sweep with an exploratory build. The kernel journal after its
  start showed, at 08:50:29 on card 0000:27:00.0:
  - `Fault response: Unsuccessful -ENOENT` (ASID 3358, EngineClass bcs: the copy engine);
  - `Engine reset: engine_class=bcs`.
- **Probable source: the previous card-27 job.** The ownrt-lab-dense agent's `bench_quant 3` microbenchmark ran under
  the card-27 lock and ended that same second. Its HALT file, recording the same two lines, is stamped 08:50:29.213.
  This engine first wrote to its output directory at 08:50:29.978 and contacted the device at 08:50:30.03. Journal
  times are second-resolution, so this is very probable, not certain.
- **Response.** Device work stopped, with no retry. The tile sweep at 256 rows was not run. The live service halts
  itself on any new fault line, so it may need attention.

## Notes
- **Rank 0 not run on device.** The driver drives rank 1 only. Rank 0's routed sites are all in formats this path
  handles: IQ4_NL/Q2_0 down, IQ2_S/IQ3_S/IQ3_XXS gate/up. Its memory at 256 rows (+191 MB of shadows) still needs the
  service's checks.
- **Synthetic routing.** The statistics come from synthetic rank-1 streams. Real text probably routes with more expert
  locality, which would mean more reuse.
- **Cold-cache JIT.** The first prefill on a cold cache JIT-compiles the new kernels, about 20 s.
- **Next levers.**
  - 512-row chunks would bring 10.6 slots per expert. They need gdn's scratch (512 x 16.8 KB > 8 MiB) grouped like
    select, and shadows of 435 MB.
  - Fuse gate and up per expert tile, so they share the bucket and the input loads.
  - Move the IQ grid tables to SLM. Decode is still most of the work at about 6 slots per expert.
