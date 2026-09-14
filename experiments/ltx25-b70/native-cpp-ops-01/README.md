# Private C++ exact ATen operators — inactive CPU prototype

**CPU operator feasibility passed: 119 cases.** No live application import, GPU/XPU initialization, runtime install, source patching outside this folder, or deployment. The private dispatcher namespace `ltx_exact_cpp_cpu01` has **CPU implementations only**. XPU/full-model/full-clip qualification remains pending.

The source was compiled once with `MAX_JOBS=1`, CPU threads 1, `with_cuda=False`, `with_sycl=False`, `-O2 -g0`. Compilation took 5.322 seconds, which is build duration and not a dispatch measurement. Source, commands, compiler output/version, runtime configuration, binary and build-file hashes are preserved in [cpu-result-01.json](cpu-result-01.json) and [cpu-build-01.log](cpu-build-01.log). Build products remain outside Git at `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-ops-cpu-01`.
The raw build log preserves the compiler's trailing space on its first line;
the source/documentation whitespace check passes with that raw log excluded.

## Contract and source delta

[native_ops.cpp](native_ops.cpp) registers new private operators. [native-ops-addition.patch](native-ops-addition.patch) records the exact addition. Frozen, byte-identical Python parents are retained under [parents](parents); their source pins are validated before any Torch import. No original operator is overridden.

| Operator | Unchanged numerical operation | Preserved checks |
| --- | --- | --- |
| RMS | `at::rms_norm(input, normalized_shape, weight, eps)` | Contiguous input/weight; static positive matching normalization shape; finite nonnegative epsilon or None; matching weight shape/dtype/device; canonical result strides/shape/dtype/device; output aliases neither input nor weight |
| Sigmoid | `at::sigmoid(input)` | Static contiguous BF16/F32 input; canonical result metadata; nonalias result |
| GELU | `at::gelu(input, approximate)` with `approximate == "tanh"` | Same activation metadata checks; explicit tanh requirement; nonalias result |

There are no new numerical formulas, reductions, fusions, copies, caches, or parameter replacements. Python parent `F.rms_norm` forwards directly to `torch.rms_norm`, whose ATen dispatcher entry is used here. Fake implementations reuse the parent's exact `_fake_native_rms`, `_fake_native_sigmoid` and `_fake_native_gelu` functions. The C++ result check also guards integer stride overflow; existing real outputs already require representable canonical strides.

The outer Python `torch.ops` call remains. This prototype removes the Python custom-op backend implementation, disabled-Dynamo wrapper, and Python metadata loops from inside that dispatch; the same checks run in C++. It does not claim to remove all Python work. Autograd/training behavior is not implemented or qualified: all execution is explicitly under inference mode. Production integration must retain the existing inference guard. Sparse/symbolic/training contracts are not broadened.

## CPU evidence

The 119 comparisons cover BF16/F32, weighted/unweighted RMS, eps None/0/1e-6/1e-5, two-dimensional normalization, scalar activations, zero-length tensors, contiguous offset views and noncanonical singleton input strides. Invalid normalization/epsilon/weight/layout/activation dtype/approximation cases reject on both parent and candidate. RMS float64 acceptance matches its broader parent contract. Accepted outputs match parent and repeat byte for byte, metadata matches, inputs stay unchanged, and output storage does not alias inputs. Three fake-mode comparisons preserve output metadata. No tolerance is used.

An optional CPU dispatcher observation also passed byte equality and input immutability before/after timing. It uses BF16 inputs, 5 sequential parent/candidate/parent triples per operation/shape, 200 calls per small interval and 40 per large interval, with both arms warmed first. These are synchronous **CPU operator plus Python dispatch** measurements, not kernel-only timings and not predictions of XPU or clip speed. The pairwise median differences differ slightly from subtracting the displayed medians.

| Operator | CPU shape | Parent mean median µs/call | Candidate median µs/call | Paired difference median µs/call |
| --- | --- | ---: | ---: | ---: |
| rms | 1×8 | 29.085 | 14.158 | -14.852 |
| sigmoid | 1×8 | 4.014 | 1.300 | -2.720 |
| gelu | 1×8 | 5.994 | 1.539 | -4.453 |
| rms | 1×64×4096 | 180.615 | 163.484 | -15.893 |
| sigmoid | 1×64×4096 | 224.999 | 214.671 | -8.544 |
| gelu | 1×64×4096 | 947.491 | 934.913 | -13.034 |

Raw intervals and byte hashes: [cpu-dispatch-timing-01.json](cpu-dispatch-timing-01.json). This small CPU observation supports continued investigation; it does not qualify a GPU speed improvement.
The larger RMS intervals are noisy: one candidate interval is slower than its
adjacent controls, and some parent intervals nearly double. Preserve those
samples; the median is not a consistent per-call saving or a clip prediction.

## Reproduction

Use new exclusive output/build paths. The fault latch is checked before importing Torch and between CPU cases; no automatic retry occurs. The preparation check writes only its explicit receipt, creates no build directory, and imports no Torch.

```bash
/home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/native-cpp-ops-01/test_cpu.py --build-dir /mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-ops-cpu-REPLAY --output /absolute/new-cpu-result.json
/home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/native-cpp-ops-01/benchmark_cpu.py --qualification /absolute/new-cpu-result.json --output /absolute/new-cpu-timing.json
```

Next qualification is an independently reviewed compiled tiny-block integration preserving original options and 15/6/2 operator boundaries, followed by XPU operator/stage/full-clip gates with a sealed binary/source identity and exclusive device scheduling. This continues the authorized optimization work. This CPU-only prototype is not an application package. No runtime reload is part of these scripts.

C++ source SHA256: `89fe1435bfbf714191150c42f42c6619a303e52b4bc8831b70c64ee6652d8652`.
Binary SHA256: `6eee2a1379b818921a1bdf980493a6eab6746dc52e885deba39c9ccfe3870280`.
