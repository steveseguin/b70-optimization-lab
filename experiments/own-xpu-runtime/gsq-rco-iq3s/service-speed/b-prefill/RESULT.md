# Batched prefill: lossless on device, 1.67× on a 581-token prompt (2026-10-24)

The serving engine is `afdfa33a9200` ([receipt](../../../engine/receipts/afdfa33a9200.json)), in F32 exact mode
with `--prefill-rows 16`. It serves the LAN endpoint through [adapter6.py](../../serving/lan/adapter6.py) with
`SC117_PREFILL_ROWS=16`. The first lossless stage was `6fd6eaa7c622`, and the progression table below lists each
binary.

## How it works (reusable parts)

- **Token-row matrix kernels.** Every matrix-multiply family takes a `tokens` count: p33 dense, kopt `gemv_tokens`, the
  gsqn packed, dense-block and IQ3 block kernels. Work-groups are ordered row-major, so all tokens that share a weight
  row run back-to-back. Each token keeps the single-token lane order, products, sums and tree. With tokens=1 the code
  computes exactly what it did before.
- **Device row views** (`ownrt::Device::row_views`). Any unchanged single-row op can run on row r of multi-row
  storage. Intermediates map to row r of a shared M-row buffer (one per role across layers; 18 MB for 16 rows on
  rank 0). `position` and `token` map to per-row arrays. Recurrent banks alternate by row parity, exactly as M
  single-token steps swap them.
- **Executor** ([prefill_engine.hpp](../../../engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/prefill_engine.hpp)).
  It runs this rank's plan launch by launch:
  - linear sites run once for all rows;
  - every other site is replayed per row;
  - QSA select and attention rows use the context extent that their own single-token step admits.
- **Transport.** Rank command 15 (`PREFILL`) carries rows through a separate versioned map, `prefill.bin`
  ([prefill_wire.hpp](../../../engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/prefill_wire.hpp)). Its forward
  and reverse regions are double-buffered. The original shared map is unchanged.
- **Controller** (`native_controller.hpp`).
  - Prompt positions 0..P−3 run in chunks. Rank 0 computes chunk k+1 while rank 1 computes chunk k.
  - Rank 0 replays the MTP draft once per confirmed prompt position, in order, from rank 1's final rows.
  - The original scalar loop then resumes at P−2, in exactly the state that its own iteration would have left. A
    request asks for this with the trailer `prefill <rows>` in `native-request.txt`.

## Device gate (service startup, one time per binary)

Evidence: [prefill-6fd6eaa7c622047d-rows16.json](../../serving/lan/evidence/prefill-6fd6eaa7c622047d-rows16.json).

1. **Token-by-token path unchanged.** The new binary reproduces the serving engine 32654dfb exactly:
   - its F32 self-test tokens are identical;
   - the first 64 outputs of two suite prompts are identical.
2. **Batched against token-by-token.** There were 11 cases, each run after a RESET:
   - chunk sizes 16, 13 and 7;
   - prompt lengths 18, 19, 34, 35, 40, 53, 66, 67, 68, 87 and 581, which cover chunk, pool and 32-token-extent
     boundaries;
   - MTP and target-only modes.

   In every case, all emitted tokens and all MTP guesses were identical. **Every buffer of the full target state dump
   on both ranks was byte-identical**, not just the persistent ones.

## Stage 1 speed (`6fd6eaa7`, same process, same prompts, prompt wall time)

| Prompt tokens | Token-by-token | Batched (16 rows) |
|---:|---:|---:|
| 34 | 951 ms | 944 ms |
| 87 (target-only) | 2,197 ms | 1,844 ms |
| 581 | 16,146 ms | 11,889 ms (1.36×) |

On the 581-token prompt, one 16-row chunk takes about 278 ms on each rank, about 17 ms per row (token-by-token: about
24 ms per token per rank). The two ranks overlap fully, and the draft replay adds about 2 ms per row on rank 0.

## Progression (all lossless: each binary passed the same startup gate, full target state byte-identical)

| Binary | Change | 581-token prompt |
|---|---|---:|
| token-by-token | none | 16.2 s |
| `6fd6eaa7` | token-row linear kernels; every other op replayed per row through row views | 11.9 s |
| `c73aeffc` | per-row replays captured as prepared commands | 11.9 s (submission was not the bottleneck) |
| `a8790dd5` | generic/specialised ops (GDN, conv, norms, QSA prepare/pool/select, HC mix, activations) run once per chunk | 10.9 s |
| `8feaa684` | dense kernels decode each weight once for 16 tokens | 12.0 s (slower; now opt-in, `OWNRT_PREFILL_REUSE=1`) |
| `43043ce7` | SimpleNew route/gather/combine multi-row by copying the binding struct per item | 31.3 s (register spill) |
| `e8823486` | the same through `RowBound` accessor offsets; status checks once over all rows | 9.7 s (1.67×) |
| `dae4f85b` | tiled kopt dense kernel: 16 weight rows per work-group, activations staged in local memory | 18.7 s (exact; slower, most likely accumulator spills; now opt-in, `OWNRT_PREFILL_TILED=1`) |
| `8a76e3ce` | tiled kernel off by default; `simple_body` reads its Spec by reference (no speed change) | 9.7 s (1.67×) |
| `afdfa33a` + `OWNRT_PREFILL_TILED=1` | tiled kernel v2: transposed local-memory tile, 16 unrolled tokens, 2 rows per subgroup | 11.0 s (exact). Per family: kopt Q8_0 0.85 → 0.73 ms/row, but 16-bit-weight sites 2.16 → 4.52 ms/row, because their matrices are mostly small-row (1–512 rows) or K=320 |
| **`afdfa33a`** | default (tiled off) | **9.7 s (1.67×)** |

Per-op profiles (`OWNRT_PREFILL_PROFILE=1`, drains after every site) are in [profiles/](profiles/). For `e8823486`, of
14.8 ms per row on rank 0:
- dense matrix multiplies take 5.3 ms;
- expert matrix multiplies take 6.0 ms;
- GDN 0.8, expert gather 0.5, attention 0.5 and HC combine 0.45 make up most of the rest.

The matrix-multiply kernels are not weight-bandwidth bound at 16 rows. Each (row, token) work-group re-decodes its
weight row and re-reads its F32 activation vector, and the work runs at a few percent of the card's FP32 peak. Weight
reuse alone (`8feaa684`) lost parallelism without removing the activation traffic.

## Next

1. Faster matrix-multiply kernels for the batched shapes. Two tiled attempts were exact but not faster overall
   (table above). The next attempt needs kernel-level measurement (a GPU profiler, or an isolated microbenchmark on a
   free card) rather than whole-service A/B runs. Then pick a kernel by shape.
   Original design idea: tiled matrix-multiply kernels. A work-group computes a block of output rows × tokens, with the activation slice
   staged once and each weight decoded once. Every output keeps its lane k-order, product then add, and its subgroup
   tree. Dense rows reuse across tokens; expert rows reuse the slot's activations across the expert's rows. The same
   tiling cuts F32 activation re-reads in single-token decode.
2. The draft replay, about 2 ms per prompt row on rank 0, as a multi-row draft step.
3. Remaining replayed ops: QSA attention (p49 counts header for more than 4 rows), MoE combine epilogue, PLE.

Each step is gated by the same startup gate.
