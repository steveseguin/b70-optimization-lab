# The text encoder's 1.45 s is fp32, not inefficiency — and what that implies

*2026-09-16, offline probes on exclusive cards
([`scripts/gemma-dtype-probe.py`](../scripts/gemma-dtype-probe.py),
[`scripts/per-device-probe.py`](../scripts/per-device-probe.py)).*

The shipped encoder runs **30.15 ms per Gemma layer**, 1447 ms per clip, against
a 0.85 ms weight-read floor. Summing its parts offline gave ~4.8 ms, so ~25 ms
per layer looked recoverable. It is not. Five hypotheses were tested and four
died:

| Hypothesis | Test | Result |
| --- | --- | --- |
| Memory pressure on a nearly full xpu:2 | rerun with 26 GB ballast resident | 3.35 -> 3.37 ms, **no effect** |
| `--deterministic` forcing slow kernels | toggle `use_deterministic_algorithms` | 3.35 -> 3.39 ms, **no effect** |
| Weights partly offloaded to CPU | placement receipt | 26.23 GB on device, `offload_buffer_bytes: 0`, **fully resident** |
| xpu:2 is a slower card | same stack on all four | 5.38 / 5.48 / 5.36 / 5.40 ms, **identical** |
| Real weight values (denormals) | load the checkpoint's own layers 0-5 | 5.41 ms/layer, **same as random** |

The fifth explains all of it. The capture receipt records
`output_dtype: torch.float32`, and the placement receipt records
`scaled_embedding` as float32: **the Gemma stack runs fp32 activations over
bf16 weights.** Rerunning the identical real stack with each activation dtype:

| Weights | Activations | ms/layer |
| --- | --- | ---: |
| bf16 | bf16 | **5.385** |
| bf16 | **fp32** | **30.648** |
| | shipped | 30.15 |

30.648 against a shipped 30.15 -- the gap is entirely the activation dtype. The
hardware reason is stark, at the MLP's own shape (1024, 3840, 15360):

| dtype | time | throughput |
| --- | ---: | ---: |
| bf16 | 0.847 ms | **142.6 TFLOP/s** |
| fp32 | 5.767 ms | **20.9 TFLOP/s** |

A **6.8x** penalty; the B70 has no fast fp32 matmul path in use here.

## What this rules out, and what it opens

Running the encoder in bf16 would be **lower precision**, which this lane
forbids outright, and it would change the bits. So the 1.45 s is not an
inefficiency to be removed -- it is the cost of the precision the model
specifies, and it stays.

That leaves exactly one lossless lever for it, and it is a good one: **the text
encoder is not on the sampler's critical path**. It occupies xpu:2; the sampler
occupies xpu:0 and xpu:1; the decoder occupies xpu:3. Cross-device concurrency
on this host is already measured at ~100% efficient. So in a continuous stream,
clip N+1's encode can run *while* clip N is sampling and clip N-1 is decoding --
every clip still computing its own encode from scratch, nothing reused, nothing
cached.

| Stage | Device | Per clip |
| --- | --- | ---: |
| Text encode | xpu:2 | 1.59 s |
| Sampler | xpu:0 + xpu:1 | 1.91 s |
| Decode + save | xpu:3 | 0.85 s |

Serial today: **4.67 s**. Pipelined, the interval becomes the slowest stage,
**~1.91 s**, i.e. **1.83 s of compute per second of video** -- from 4.48,
without caching anything.

The sampler is then the entire problem, and its own floor is 0.74 s against the
1.042 s budget. Closing that last gap means attacking the ~60% of block time
that is not GEMM.
