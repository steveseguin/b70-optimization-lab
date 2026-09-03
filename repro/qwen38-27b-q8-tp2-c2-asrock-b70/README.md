# Reproduce Qwen3.8 27B Q8_0 target-only TP2 at concurrency two

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

This is a service-throughput companion to the primary
[single-request Q8 reproduction](../qwen38-27b-q8-tp2-asrock-b70/README.md).
It runs the same accepted model, binary, source patch, runtime, TP2 split,
F16 KV, and no-speculation configuration with two server slots.

## Captured result

Two independent captures, each using two synchronized 256-token requests:

| Run | Request 0 | Request 1 | Aggregate conventional | Aggregate wall |
| --- | ---: | ---: | ---: | ---: |
| 1 | `28.699956` | `28.699486` | **`57.398122 tok/s`** | `56.488104 tok/s` |
| 2 | `28.727575` | `28.700991` | **`57.397626 tok/s`** | `56.511198 tok/s` |

Both runs were cache-cold (`cache_n=0`), had fairness above `0.999`, and
returned token IDs exactly equal to a same-server sequential oracle for each
prompt. There is no MTP, DFlash, draft model, speculative decoding, prompt
reuse, response reuse, or KV reuse.

This is an aggregate service-capacity result, **not** a 57 tok/s single-stream
claim. Each concurrent request delivered about 28.70 tok/s. It is also a
two-prompt cross-batch gate, not proof that every prompt is schedule-invariant.
Broader c2 experiments observed schedule-dependent greedy outputs. A later
batch-shape sweep confirmed the boundary directly: `2048/512` matched both
sequential oracles twice for the captured pair above, but matched 0/2 for a
disjoint fixed-prompt pair. This result is therefore not a general arbitrary-
prompt quality guarantee. See the [batch-shape audit](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-batch-shape-audit.md)
and [cache-row fusion note](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md).

## Exact identity

- model SHA-256: `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- `llama-server` SHA-256: `32c581628082fa1352824650d45f523d52b526aaefdfd23e1c34d438f7ad084a`
- accepted source base and patch: [Q8 patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md)
- reasoning mode: off
- API: native llama.cpp `/completion`
- server: `--parallel 2 --ctx-size 16384 -b 1024 -ub 256`
- GPUs: two ASRock Intel Arc Pro B70 32 GiB, equal tensor split

## Run

Start the endpoint:

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-c2-asrock-b70/run-server.sh
```

After `/health` reports ready, capture a two-request result:

```bash
OUT=/path/to/c2-result.json \
  repro/qwen38-27b-q8-tp2-c2-asrock-b70/bench.sh
```

The harness first records cache-cold sequential token-ID oracles, then opens
two HTTP connections and releases them through one synchronization barrier.
It fails unless both concurrent outputs are exactly equal to their sequential
oracles and all cache counters are zero.

Research replays may override `QWEN38_C2_BATCH` and `QWEN38_C2_UBATCH` when
starting the server. The default remains the captured `1024/256`; the sweep did
not establish a faster or universally exact replacement. Use
`--prompt-offset 2` with the underlying capture script to exercise the second
disjoint fixed-prompt pair.

The compact accepted evidence is
[`2026-08-16-q8-tp2-c2-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-16-q8-tp2-c2-summary.json).
