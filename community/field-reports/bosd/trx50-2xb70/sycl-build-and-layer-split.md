# SYCL build freshness and layer-split regression report

> **Evidence: `community-reported`; not run in the reference lab.** The report
> suggests a useful regression window, but it is not a completed bisect and the
> newest reported build identity is unresolved.

Contributor source snapshot:
[`fda0d86c47ff02d8e36f813a8e0121a2152d4478`](https://github.com/bosd/trx50-arc-b70-benchmarks/tree/fda0d86c47ff02d8e36f813a8e0121a2152d4478).
The submitted field report itself is preserved in contributor commit
[`f56bb4070`](https://github.com/steveseguin/b70-optimization-lab/commit/f56bb4070cdfba23b9057f9908dbd0dabe3ea1b4).

## Reported build comparison

The contributor reports one Arc Pro B70, Qwen3-30B-A3B-Instruct-2507
UD-Q4_K_XL, flash attention on, and `llama-bench` prompt length 512/generation
length 128:

| Reported build | tg128 tok/s | pp512 tok/s |
| --- | ---: | ---: |
| b9455 | 84.7 | 1287 |
| dee2a84 | 97.0 | 1383 |
| 11924d4 | 100.6 | 1393 |

The like-for-like change from 84.7 to 100.6 tok/s is **+18.8%**, not +27%.
The separate 79 tok/s starting point used for the +27% headline was an older
Qwen3 model and Q4_K_M quantization, so that comparison changes the build,
model, and quantization together.

During maintainer review, llama.cpp tag `b9455` resolved to commit
[`8e6fff84de4a31506e0f90bacbf821731e66d237`](https://github.com/ggml-org/llama.cpp/commit/8e6fff84de4a31506e0f90bacbf821731e66d237)
and `dee2a84` resolved to
[`dee2a846b82f15d27f84a48fa387cb53e0d99c25`](https://github.com/ggml-org/llama.cpp/commit/dee2a846b82f15d27f84a48fa387cb53e0d99c25).
`11924d4` did not resolve as a commit in the upstream GitHub repository and is
therefore retained only as an unknown contributor build identifier.

## Reported two-GPU failure window

For Qwen3.6-35B-A3B Q8_0 with two B70 GPUs and llama.cpp `-sm layer`, the
contributor reports:

| Build | Kernel 7.0.10 | Kernel 7.1.5 |
| --- | --- | --- |
| b9455 | works, about 26 tok/s | works, about 26 tok/s |
| dee2a84 / 11924d4 | `ggml_backend_tensor_copy` SIGABRT | same SIGABRT |

The same good/bad outcome across two kernels is consistent with a llama.cpp or
build-stack regression appearing by `dee2a84`, rather than a failure caused
solely by the kernel switch. Without committed raw crash logs, exact binary
manifests, controlled rebuilds, or an actual `git bisect`, it does not identify
the regressing commit or exclude other build/runtime differences.

The narrow useful output is a community-supplied candidate window from
`b9455`/`8e6fff84` to `dee2a84`/`dee2a846` for investigation alongside
[`ggml-org/llama.cpp#23797`](https://github.com/ggml-org/llama.cpp/issues/23797).

## Reported batched throughput at concurrency

Separate from the single-stream and two-GPU results above, the contributor ran
`llama-batched-bench` on one B70 to measure aggregate throughput versus parallel
request count. Qwen3-30B-A3B-Instruct-2507 UD-Q4_K_XL, `-npp 128 -ntg 128 -fa 1`,
build `11924d4`:

| Parallel (npl) | Generation tok/s (aggregate) | Total tok/s (incl prompt) |
| --- | --- | --- |
| 1 | 65.7 | 115.8 |
| 4 | 110.7 | 199.8 |
| 16 | 202.5 | 354.1 |
| 32 | 299.8 | 495.2 |
| 50 | 382.7 | 601.5 |

The contributor offers this as one single-B70 data point against community
reports of roughly 370 tok/s (peaks near 550) at fifty-way concurrency: here
382.7 generation / 601.5 total tok/s on plain llama.cpp continuous batching, for
a 3B-active MoE. It is not a controlled reproduction of any specific third-party
report — model revision and engine differ, and a dense model or vLLM-XPU would
shift the prompt/generation mix — but the batched-throughput ceiling on one card
is in that range. Prompt processing held near 1400 tok/s across the sweep.
