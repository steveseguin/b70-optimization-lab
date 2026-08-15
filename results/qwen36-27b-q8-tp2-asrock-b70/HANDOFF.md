# Qwen3.6 27B Q8 TP2 Handoff

Status: **active target-only optimization on 2026-08-15**

## Resume Bookmark

The accepted target-only two-B70 result is:

| Field | Accepted value |
| --- | --- |
| Conventional 99-interval median | **`36.347290 tok/s`** |
| Historical helper | `36.714434 tok/s` |
| Full-512 after-TTFT median | `36.365074 tok/s` |
| Quality | 12/12 cold 512-token outputs byte-exact to the accepted control |
| Cache | `cached_tokens=0` for 12/12 |
| Target | Qwen3.6 27B GGUF Q8_0 |
| Runtime mode | target-only TP2; no MTP, DFlash, draft, or reuse |
| Source base | mndodd llama.cpp `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` |
| Complete decoded patch SHA-256 | `c8ae065cabf9e7b7f6b6a224673498ddf82b07aeb1d16a33d341368b9b3234d7` |

Start with the [result packet](README.md), then use the
[standalone reproduction](../../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
and [source patch](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md).

## Pass 1 And Pass 2

The complete chronological record is
[`notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md`](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md).
It remains the authority for commands, exact A/B values, failure signatures,
and raw log paths. Pass 1 promoted no replacement. The
[pass-2 ledger](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md) records
the register-direct Q8 handoff, direct IMRoPE-to-KV-cache fusion, and vec4 TP
root reduction that passed a clean rebuild and complete 12-prompt exact-output
suite. It now also records the exact SIMD16 Q/K RMS+scale+IMRoPE fusion. Its
local FP32 materialization version is `+0.741%` over the preceding clean
record and passes 12/12 complete hashes; the faster barrier-free version is
quality-rejected. The current record adds recurrent conv+SiLU+paired Q/K-L2
fusion: `+0.322%` conventional and `+0.494%` full-512 over that prior record,
with 12/12 complete hashes exact and 588,672/588,672 eligible rank-layer hits.

Closed hypotheses include:

- dual-peer, root-fused, alternating-root, pre-norm, and last-event collective
  variants;
- deep-batch/reorder, SIMD32, scale-sharing, unequal split, FFN row/interleave,
  and fused epilogue variants;
- Level Zero synchronization, command-list, copy-offload, adapter, and dispatch
  knobs;
- parallel rank submission, host polling, CPU affinity/thread-count, and
  explicit collective workgroups;
- FlashAttention vector-depth and multiple recurrent/GDN producer/consumer
  fusions;
- power, clock, and scheduler explanations.

The built-in TP2 SYCL profiler and the root-both remote-write prototype caused
device faults/resets. Do not retry them. Other doors were neutral or slower and
remain default-off/reverted.

## Remaining Gap

Long direct repeats remain around the `36 tok/s` class, while the rough Q8 HBM
roofline is about `42.5 tok/s`. The remaining gap is dominated by the streamed
Q8 model and TP2 cross-bridge execution; the tested command-count, host, and
small-kernel changes did not produce a stable large gain. Recycling the same
rejected flag/kernel neighborhood is unlikely to justify another full
validation cycle. The 40 tok/s stretch goal requires a materially new exact
critical-path reduction, not speculation or benchmark reuse.

Prioritize one of these materially new inputs:

1. a new Qwen checkpoint or quantization identity with its own quality gate;
2. a public SYCL/oneDNN/runtime change with a bounded, source-backed hypothesis;
3. a different interconnect/topology;
4. a new exact kernel design with a standalone critical-path result large
   enough to move the end-to-end record.

## Protected State

- Accepted source: `/mnt/fast-ai/src/llama.cpp-q8-tp2-outputhead-sg32`
- Prior control source: `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`
- Accepted model:
  `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/Qwen3.6-27B-Q8_0.gguf`
- Prior promoted evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion`
- Pass-1/pass-2 and current promoted evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260815-outputhead-sg32`

Inspect source status and service/process ownership before using these paths.
Do not reset them, replace the accepted build, or delete raw evidence during a
new model bring-up.

## Main-Only Workflow

All repository updates belong directly on `main`. Use focused commits, source
patches, result packets, and external build/source directories for experiment
isolation. Do not create a Git branch or secondary worktree for a reopened Qwen
experiment.
