# Packet 66: fast+save reproduces at 2.049 s; the batch-2 proof's stacked call failed inside the model

*2026-09-17 05:05–05:08 UTC, server PID 52664. Evidence:
[`data/graph-capture-66/`](../data/graph-capture-66/).*

| Arm | Prompts | Distinct | Exact | Steady interval |
| --- | ---: | ---: | --- | ---: |
| `pipe-batchproof` (three forwards per step, diagnostic) | 3 | 2 | 2/2 | 9.66 s (not a speed result) |
| `pipe-fast-save` (repeat of packet 65) | 12 | 11 | **11/11** | **2.049 s** |

The clips under the proof wrapper stayed exact, because the wrapper returns
the original batch-1 result. The proof itself did not run: on every forward
the stacked batch-2 call failed with `shape '[2, -1, 8192]' is invalid for
input of size 8192`, an 8192-element (one-row) tensor being viewed with a
batch of two, i.e. some batch-carrying input reached the model unstacked.
The candidates are ComfyUI's per-batch lists inside `transformer_options`
(`cond_or_uncond`, `uuids`), which the wrapper deliberately did not walk.
Packet 67 records the traceback and a shape census of every argument, doubles
those lists for the stacked call, and runs the proof alone.

Why this proof matters: the blocks are weight-read bound (1.57 s of the
2.03 s clip). If a batch-2 forward is bitwise equal, row for row, to two
batch-1 forwards on this stack, two clips can share every weight read and the
per-clip block cost roughly halves with no arithmetic change. If it is not,
batching is closed under the lossless rule and the two-clip scheduler is the
remaining route.
