# Batched prefill, stage 1: lossless on device, 1.36× on a 581-token prompt (2026-10-24)

Engine `6fd6eaa7c622` ([receipt](../../../engine/receipts/6fd6eaa7c622.json)) in F32 exact mode, with
`--prefill-rows 16`. It serves the LAN endpoint through [adapter6.py](../../serving/lan/adapter6.py) with
`SC117_PREFILL_ROWS=16`.

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

## Speed (same process, same prompts, prompt wall time)

| Prompt tokens | Token-by-token | Batched (16 rows) |
|---:|---:|---:|
| 34 | 951 ms | 944 ms |
| 87 (target-only) | 2,197 ms | 1,844 ms |
| 581 | 16,146 ms | 11,889 ms (1.36×) |

On the 581-token prompt, one 16-row chunk takes about 278 ms on each rank, about 17 ms per row (token-by-token: about
24 ms per token per rank). The two ranks overlap fully, and the draft replay adds about 2 ms per row on rank 0.

## Next

Most of a row's time is host submission. Every non-linear op is replayed through the direct (unprepared) submission
path, about 600 ops per row. Next steps:
1. Capture the per-row replays as prepared commands, as the decode path already does.
2. Then give the hot ops native multi-row launches, keeping each one's arithmetic unchanged.

Each step is gated by the same startup gate.
