# Qwen3.8 27B Q4_K_M TP1 raw batched ladder preregistration

Date: 2026-08-25

Status: **preregistered; no performance result recorded here.**

This campaign fills the missing one-card aggregate-decode measurement for the
validated Qwen3.8 27B Q4_K_M stack. It measures `llama-batched-bench` at
parallel-sequence counts `1,2,4,8,16,32,64`, with 128 prompt tokens and 256
generated tokens per sequence. Each row is a direct measurement. Missing
points remain missing; no curve fitting, interpolation, or extrapolation is
allowed.

The complete frozen contract is the adjacent
[manifest](../data/2026-08-25-qwen38-q4km-tp1-batched-ladder-r1.json). The
portable launcher is
[`run-qwen38-q4km-tp1-batched-ladder.sh`](../scripts/run-qwen38-q4km-tp1-batched-ladder.sh).
It requires explicit `MODEL_DIR`, `SOURCE_DIR`, and `BUILD_DIR` rather than
embedding this lab host's mount paths.

## Identity boundary

The source is reconstructed from the public package recipe: mndodd base
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` plus the six lab patch artifacts
whose decoded identities are checked by
[`restore-and-build.sh`](../../../repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh).
The applied aggregate diff SHA-256 is
`f24d58bfddb12e7263c2b6974ce8fe2114b47d831f57fe329207ec0edb2f705e`.

This attempt uses Intel oneAPI compiler **2026.1.1**. The promoted TP1 server
headline used 2026.0.0, so this is deliberately a new experimental identity;
the numbers cannot be silently pooled with the 27.82 tok/s endpoint result.
The clean rebuild itself found and fixed a publication defect: selecting
`icpx` without sourcing oneAPI left IntelSYCL and MKL undiscoverable in a
fresh shell. The recipe now initializes oneAPI and builds
`llama-batched-bench` explicitly.

## What this does and does not prove

`speed_tg` is aggregate generated-token throughput across the measured number
of parallel sequences. `speed_tg / pl` is a same-row arithmetic derivative,
not a new measurement. The program feeds random token IDs and does not retain
model outputs. Therefore this ladder is useful for finding the compute and
memory-throughput ceiling, but it is **not** user-facing concurrent-serving
evidence and has no output-quality claim. Any promising setting must be
replayed through `llama-server` with distinct prompts, sequential oracles,
freshness checks, and complete output capture.

## Portable invocation

After rebuilding through the package recipe:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
SOURCE_DIR=/path/to/patched/llama.cpp \
BUILD_DIR=/path/to/patched/llama.cpp/build-sycl-aot-bmg-g31 \
OUT_DIR=/path/to/results \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-batched-ladder.sh
```

The launcher refuses a model or source mismatch, an occupied GPU, a competing
model process, missing oneAPI initialization, an existing output directory,
or malformed/missing matrix rows.

## Attempt log

- Attempt 1 closed `failed-incomplete-preload` with zero performance rows. The
  pinned tool rejected the unsupported double-dash `--npp` spelling before
  model load or GPU work. The corrected launcher uses its documented
  single-dash `-npp/-ntg/-npl` forms without changing the frozen matrix. The
  [failure record](../data/qwen38-q4km-tp1-batched-ladder-20260825-r1-attempt1/failure.json)
  retains the cause and boundary. A too-broad environment capture from that
  attempt was removed; subsequent attempts record only a non-secret runtime
  whitelist.
- Attempt 2 completed all seven frozen rows. The result and interpretation are
  in the [result note](2026-08-25-qwen38-q4km-tp1-batched-ladder-result.md);
  the highest directly measured raw-engine aggregate was `95.411842 tok/s` at
  64 parallel sequences.
