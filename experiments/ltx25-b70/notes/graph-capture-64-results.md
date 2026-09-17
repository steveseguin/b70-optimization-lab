# Packet 64: skipping model-management bookkeeping for resident models, 2.52 → 2.13 s per clip, exact

*2026-09-17 04:37–04:42 UTC, server PID 6677, boot `09862e00…`. Evidence:
[`data/graph-capture-64/`](../data/graph-capture-64/), committed after every
arm.*

| Arm | Prompts | Distinct | Exact | Steady interval | p95 | Effective fps |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| warm clip (`pipe`, boat) | 1 | 1 | yes | — | | |
| `pipe-fasttimed` (bookkeeping timed, unchanged) | 12 | 11 | **11/11** | 2.544 s | | 9.8 |
| `pipe-fast` (resident fast path on) | 20 | 19 | **19/19** | **2.135 s** | 2.30 s | **11.7** |
| `pipe-up-save`, `pipe`, `pipe-fwdtimed` | — | — | — | not run: the fast-path gate's `original` mode refused to run while the fast path was installed, and that latch is sticky | | |

## What the timed arm measured

Every `comfy.model_management.load_models_gpu` call during a clip, with all
five models already fully resident on their cards (11 clips):

| Caller | Per call |
| --- | ---: |
| transformer, before stage-A sampling | **0.31–0.53 s** |
| transformer, before stage-B sampling | 0.004 s |
| latent upsampler | 0.05–0.07 s |
| VAEs, text encoder | 0.001–0.004 s |
| **per clip** | **0.42 s mean** |

The stage-A call is expensive and the stage-B call is not, so the cost is not
the call itself but what the previous prompt's teardown leaves behind
(ComfyUI empties the device cache after every prompt, and the next
`free_memory` pays to re-establish allocator state and re-walk the sharded
model's module list). None of it touches a tensor value.

## The fast path

`LTXResidentFastPath` replaces the function with one that returns
immediately when every requested model is a live, fully loaded, non-dynamic
entry of `current_loaded_models` with no additional patch models, and defers
to the original otherwise. In the `pipe-fast` arm every call was skipped
(receipts: `skipped == count`). The interval fell from 2.52 s (packet 58) and
2.544 s (this packet's timed control) to **2.135 s**, and all 19 distinct
clips matched their references byte-for-byte. Nothing was cached, reused or
approximated: the same kernels ran on the same data; only bookkeeping that
had no effect on a resident model was skipped.

## Standing position

| | per distinct clip | wall per second of video | fps equivalent |
| --- | ---: | ---: | ---: |
| packet 58 three-stage pipe | 2.519 s | 2.42 s | 9.9 |
| **packet 64 + resident fast path** | **2.135 s** | **2.05 s** | **11.7** |
| goal | 1.042 s | 1.00 s | 24 |

## Runner defect, again

A gate's `original` mode refused to run after an arm that had installed it,
for the third time in this lane (upsampler gate in packet 61, fast-path gate
here). Every gate's `original` mode now restores the original state itself
and records `restored_from`; the packet 65 runner combines the fast path with
save-behind (`pipe-fast-save`), repeats `pipe-fast`, runs the `pipe` control,
and ends with the forward-timing diagnostic.
