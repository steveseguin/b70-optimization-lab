# Single-B70 synthetic batched-decode throughput

> **Evidence: `community-reported`; not run in the reference lab.** This is a
> `llama-batched-bench` microbenchmark, not a serving or request-concurrency
> test. No raw benchmark output was supplied.

The contributor supplied this follow-up in
[PR #17](https://github.com/steveseguin/b70-optimization-lab/pull/17), commit
[`a1bb15c23`](https://github.com/steveseguin/b70-optimization-lab/commit/a1bb15c23018b17504f57f2e4d1bff0ad984cd0c).
It does not appear in the collection's pinned external source snapshot.

## Reported identity

- Hardware: one Intel Arc Pro B70 from the contributor's TRX50 host.
- Model: Qwen3-30B-A3B-Instruct-2507 UD-Q4_K_XL. Exact model repository,
  revision, GGUF source, and file hash: not supplied.
- Engine: llama.cpp contributor build identifier `11924d4`, which did not
  resolve as an upstream commit during maintainer review.
- Supplied arguments: 128 prompt and 128 generation tokens per sequence via
  `-npp 128 -ntg 128`, plus `-fa 1`; parallel-sequence values 1, 4, 16, 32,
  and 50.
- Full command, context size, logical/physical batch sizes, GPU offload/device
  arguments, prompt-sharing mode, repeat count, dispersion, cold/warm state,
  and raw output: not supplied.
- Quality scope: none. The benchmark feeds random token IDs into its prompt and
  generation steps and does not sample or produce text that can support a
  semantic quality claim.

## Reported measurements

| Parallel sequences (`npl`) | `S_TG` generation tok/s | `S` combined tok/s |
| ---: | ---: | ---: |
| 1 | 65.7 | 115.8 |
| 4 | 110.7 | 199.8 |
| 16 | 202.5 | 354.1 |
| 32 | 299.8 | 495.2 |
| 50 | 382.7 | 601.5 |

`S_TG` is aggregate generation throughput across the parallel sequences. `S`
combines prompt and generation tokens over their combined elapsed time. At the
largest tested `npl`, those reported metrics are 382.7 and 601.5 tok/s,
respectively. They are not per-sequence rates, latency, server goodput, or
evidence that fifty independent requests completed. Throughput was still
rising at the last row, so the sweep does not establish a ceiling.

## Maintainer review

The
[Qwen model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
identifies the model family as 30.5B total and 3.3B activated parameters. The
upstream
[`llama-batched-bench` implementation](https://github.com/ggml-org/llama.cpp/blob/3581ba0cf591b3f772fbb002de0f70e294bc0396/tools/batched-bench/batched-bench.cpp)
uses random token IDs, statically interleaves `npl` sequences, and defines the
reported `S_TG` and `S` formulas. This supports the metric interpretation, not
the contributor's performance numbers or unknown build identity.

Using those formulas with the rounded supplied values implies prompt-processing
rates of approximately 488, 1,024, 1,409, 1,422, and 1,405 tok/s for `npl`
1, 4, 16, 32, and 50. Prompt processing therefore approached and held near
1,400 tok/s only from `npl=16` onward, not across the entire sweep.

The PR body compared the largest row with unspecified community reports around
370 tok/s and peaks near 550 tok/s. No durable source or matching metric
identity was supplied, so that comparison is not adopted here. This page
preserves the five reported microbenchmark rows only; it is not a controlled
reproduction or a server-capacity claim.
