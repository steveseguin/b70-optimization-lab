# Qwen3.8 27B Q8_0 — two-B70 candidate package

This is the quality-conservative Qwen3.8 service package: Q8_0 target weights,
F16 KV, two B70s, no draft model, and no speculative decoding. The accepted
historical suite measured `36.772932 tok/s` conventional median with 12/12
exact output hashes and zero cached tokens.

> **Strict package headline pending.** That historical suite ran with
> reasoning enabled, while this package launches with reasoning off. It is
> valid evidence for its recorded identity, but it is not the packaged
> identity's headline. The exact package still needs the complete varied-prompt
> 512-cap suite on two fresh servers plus its bound quality/determinism gate.

> **Status: expert candidate; strict headline pending.** The model and patch identities, source build,
> service launcher, benchmark, and semantic gates are documented. Platform
> installation, a model download/direct-read helper, and clean-host replay are
> still missing.

The [reproduction guide](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
is the technical source of truth.

## Who built what

**neural.download lab — integrated:** Qwen3.8 transfer, the complete B70 TP2
stack, DP4A2 by SG24 optimization, semantic/repeat/needle gates, benchmarking,
and packaging. The matched Qwen3.8 transfer comparison measured `36.772932`
versus `31.353431 tok/s` (`+17.285%`) with all output hashes exact.

**mndodd — integrated runtime base:** supplied the optimized Intel SYCL
llama.cpp fork used as the starting runtime. A separate matched Qwen3.6 A/B
validated `+5.836%` for that base. That credit is deliberately scoped and does
not assign the lab's later Qwen3.8 result or patches to the base fork.

## Exact route

Download `Qwen3.8-27B-Q8_0.gguf` from revision
`0669b98607d47046c7c2b3f801011d54a08cfccf` and require:

```text
bytes    28595763552
sha256   f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8
```

Restore the runtime base and apply the three project artifacts listed in the
[patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md). Build
with the exact oneAPI/CMake settings in the reproduction guide, then audit the
packet:

```bash
repro/qwen38-27b-q8-tp2-asrock-b70/verify-artifacts.sh
```

Launch in a dedicated terminal:

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-asrock-b70/run-server.sh
```

Then check and benchmark:

```bash
curl -fsS http://127.0.0.1:18088/health
OUT=/path/to/result.json repro/qwen38-27b-q8-tp2-asrock-b70/bench.sh
```

The historical accepted capture was reasoning-enabled. The packaged service
defaults to `--reasoning off`, which is intentionally a different benchmark
identity. Do not compare the two without recording that setting, and do not use
the historical number as this package's headline.

## Output-audited multi-user profile

For throughput service, launch the separately qualified 64-slot, 32K-total
profile:

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-asrock-b70/run-throughput-server.sh
```

| Simultaneous requests | Aggregate tok/s | Per-user tok/s |
| ---: | ---: | ---: |
| 1 | 32.487 | 32.487 |
| 2 | 51.601 | 25.801 |
| 4 | 85.595 | 21.399 |
| 8 | 125.414 | 15.677 |
| 16 | 84.329 | 5.271 |
| 32 | 125.832 | 3.932 |
| 64 | **163.644** | 2.557 |

Every point is the median of two preregistered fresh-server attempts; the
worst relative range was 1.46%. Each response returned 128 raw token IDs,
cached-token reuse was zero, and no output collided with another base task's
frozen oracle. Greedy output remains batch-shape-dependent. The reproduced
c8-to-c16 drop is deliberately not smoothed. These are aggregate batch-wall
rates, not queued TTFT or per-request latency. See the
[evidence](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-http-concurrency-r2-result.json).

## Exact active-context profile

The one-slot, reasoning-off HTTP service was also replayed at exact prompt
depths. Each receipt returned 128 token IDs with zero cache reuse, no
truncation, and no context shift. Server-reported prompt evaluation was
captured directly; it is not estimated from TTFT.

| Prompt tokens | Decode tok/s | Prefill tok/s | TTFT |
| ---: | ---: | ---: | ---: |
| 2,048 | 36.797 | 1,032.33 | 2.003 s |
| 4,096 | 36.553 | 1,038.62 | 3.957 s |
| 8,192 | 36.014 | 1,019.69 | 8.047 s |
| 16,384 | 35.085 | 983.52 | 16.681 s |
| 24,576 | 34.519 | 947.33 | 25.958 s |
| 32,768 | **33.849** | 915.09 | 35.832 s |

This is a grade-C repeated-token exact-shape fixture, not a natural-prose
latency claim. Every marker is measured; no interpolation or extrapolation is
used. See the [qualified replay](../../experiments/qwen38-27b-b70/data/qwen38-q8-tp2-http-depth-prefill-20260825-r3-attempt1/summary.json).

## Certification gaps

The remaining work is a tested host installation path, clean-host replay,
beginner recovery guide, natural-prompt HTTP context curves, and queued
TTFT/per-request latency.
