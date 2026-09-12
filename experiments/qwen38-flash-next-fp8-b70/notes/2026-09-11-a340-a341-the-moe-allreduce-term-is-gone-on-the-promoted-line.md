# A340 / A341: the data-dependent MoE all-reduce term is gone on the promoted line

Preregistration: `2026-09-11-a340-a341-moe-allreduce-on-the-promoted-line-prereg.md`. Both arms
derive from the promoted MTP0 packet A336 (W13-N64, full decode graphs, headroom placement,
Triton HC, fused QSA) on the diagnostic head `17710613` = `2a372e86` + report-only hooks
(step timing, per-site all-reduce events, skip switches, memory note). Three exact-2K rows each.

| arm | MoE final all-reduce | graph M=1 forward, exact-2K | row rate | exact-2K output |
| --- | --- | ---: | ---: | --- |
| A340 | real | **27.2 ms** median (26.9-29.0, n=152) | 33.32 tok/s conventional | `afffd211…` x3 = authority |
| A341 | static zero buffer (timing only) | **27.3 ms** (27.0-28.7, n=152) | - | garbage by construction |
| A342 | skipped entirely (timing only) | **26.5 ms** (26.0-26.8, first row) | - | garbage by construction |

Prefill chunks (64 tokens): 355 vs 345 ms. Sampler 0.85 ms. The step distribution is tight in both.

## What it says

On 2026-09-05 (`f8c7c0ee`, before headroom placement) the same pair read 72.7 vs 34.2 ms and the
lane concluded that ~40 ms of the step sat at the 48 MoE all-reduces only when the reduced data was
real. On the promoted line the two arms are equal to within noise. The "data-dependent collective"
was therefore never the collective: it was the driver paging cold expert buffers on the real routing
(the VRAM-full cliff documented on 09-05), and the headroom and expert-placement promotions that
ended the paging also removed the term. The diagnostic head did not change numerics (A340's outputs
equal the authority on every row), so the promoted line's step is what this measures.

Instrument note: `Q38_ALLREDUCE_EVENT_TIMING` cannot be read on a graph line (XPU events recorded
inside graph replay have no profiling information); attribution on graph lines is by differencing,
which is what A340/A341 did. A342 (all-reduce skipped entirely) bounds the collective's mechanical
cost at **~0.7 ms of the 27.2 ms step (2.6%)**: the 48 MoE all-reduces are not a lever on this line; A343 measures the two-row MTP1 verify step on the promoted fused-QSA line, the last
single-user term the lane has not re-measured since the September promotions.

## Evidence

- `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/...-mtp0-4352-ple-only-r1-attempt340/`
  and `...-attempt341/`: `server.log` (Q38_STEP_TIMING lines), `exact-depth-2k-r{1,2,3}.json`,
  `step-timing-2k.json`.
- Packets: `tools/rewrite-q38-a336-to-diag-allreduce-site-timing.py`, `tools/*a340*`, `tools/*a341*`,
  `tools/q38-timing-driver.sh`.
