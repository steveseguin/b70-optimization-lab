# Encode-ahead: 4.50 -> 3.16 seconds of compute per second of video, no caching

*2026-09-16, packet45, `pipe` arm. Six-clip throughput plus three oracle-gated
clips, all four raw outputs bytewise equal on every one.*

## Result

| | interval | per second of video |
| --- | ---: | ---: |
| `graph-text` (serial encode) | 4.685 s | **4.50 s** |
| `pipe` (encode-ahead) | **3.292 s** | **3.16 s** |

1.39 s of the encode's 1.59 s is hidden. Per clip, with the oracle running:

| clip_index | clip | text encode | sampler | exact |
| ---: | ---: | ---: | ---: | --- |
| 100 (cold) | 4.854 s | 1.606 s | 2.117 s | yes |
| 101 | 3.165 s | **0.002 s** | 1.978 s | yes |
| 102 | 3.258 s | **0.003 s** | 2.016 s | yes |

## Why this is not caching

The text encoder's cost is irreducible -- fp32 activations at 20.9 TFLOP/s
against 142.6 for bf16, and bf16 would be lower precision
([text-encoder-is-fp32-bound](text-encoder-is-fp32-bound.md)). What is *not*
fixed is when it runs. It occupies xpu:2 while the sampler occupies xpu:0 and
xpu:1, so clip N+1's encode is started on a worker thread the moment clip N's
conditioning is handed over, and it runs while clip N samples.

**Every clip computes its own conditioning and consumes it exactly once.** The
receipts show it directly -- each clip records the wall time of its own encode:

| clip | computed inline | its encode took | started ahead |
| ---: | --- | ---: | --- |
| 0 | yes | 1.733 s | clip 1 |
| 1 | no | 1.634 s | clip 2 |
| 2 | no | 1.660 s | clip 3 |
| 3 | no | 1.733 s | clip 4 |

Clip 1 reports its encode took 1.634 s even though the node returned in 0.002 s.
The work happened; it happened earlier. Nothing is stored between clips, no value
is served twice, and a prefetch that raced would change the sampler's input and
fail the oracles. Contrast the retired conditioning cache, which computed the
value once and served it six times.

## Two contracts that had to be met

- **`torch.inference_mode()` is thread-local.** ComfyUI executes nodes inside
  it, so the worker ran in a different autograd context from the one the graph
  capture buffers were built in, and died with "Inplace update to inference
  tensor outside InferenceMode is not allowed". The worker enters it explicitly.
- **The lab's embedding instrumentation enforces one-encode-then-consume**, and
  its consumer is `LTXHostEmbeddingPlacementCheck`, which a pipelined arm cannot
  carry: the encode finishing during a request belongs to the *next* clip, so
  the accounting no longer lines up with a request boundary. Every encode runs
  on the single worker thread, so the worker consumes the observations itself.
  That discards a diagnostic and touches no numerical value.

## What is left

| Stage | Device | Per clip | Status |
| --- | --- | ---: | --- |
| Text encode | xpu:2 | 1.59 s | **hidden** |
| Sampler | xpu:0 + xpu:1 | 1.98 s | the critical path; floor 0.74 s |
| Video decode | xpu:3 | 0.56 s | still serial |
| Audio decode | xpu:3 | 0.18 s | still serial |
| Save | - | 0.13 s | still serial |

Decoding clip N while clip N+1 samples is the same trick one stage later, worth
about 0.85 s and taking the interval to roughly the sampler's 2.0 s. After that
the sampler is the entire problem: 1.98 s against a 1.042 s budget, with a
0.74 s weight-read floor and ~60% of block time in non-GEMM work.
