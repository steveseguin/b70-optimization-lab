# Qwen3.6 27B Q8 TP2 Handoff

Status: **closed and banked on 2026-08-14**

## Resume Bookmark

The accepted target-only two-B70 result remains unchanged:

| Field | Accepted value |
| --- | --- |
| Conventional 99-interval median | **`35.699225 tok/s`** |
| Historical helper | `36.059823 tok/s` |
| Full-512 after-TTFT median | `35.715918 tok/s` |
| Quality | 12/12 cold 512-token outputs byte-exact to the accepted control |
| Cache | `cached_tokens=0` for 12/12 |
| Target | Qwen3.6 27B GGUF Q8_0 |
| Runtime mode | target-only TP2; no MTP, DFlash, draft, or reuse |
| Source base | mndodd llama.cpp `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` |
| Complete decoded patch SHA-256 | `710b8628f6c94025d9a0516f77bddeeebccdd27d5bd3ebc4f79d2e623b1dd6c7` |

Start with the [result packet](README.md), then use the
[standalone reproduction](../../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
and [source patch](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md).

## Post-Record Pass 1

The complete chronological record is
[`notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md`](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md).
It remains the authority for commands, exact A/B values, failure signatures,
and raw log paths. Pass 1 did not promote a replacement for the accepted
recipe.

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

## Why The Lane Is Closed

Long direct repeats remain around the `36 tok/s` class, while the rough Q8 HBM
roofline is about `42.5 tok/s`. The remaining gap is dominated by the streamed
Q8 model and TP2 cross-bridge execution; the tested command-count, host, and
small-kernel changes did not produce a stable promotable gain. Reopening the
same flag/kernel neighborhood is unlikely to justify another full validation
cycle.

Reopen only for one of these materially new inputs:

1. a new Qwen checkpoint or quantization identity with its own quality gate;
2. a public SYCL/oneDNN/runtime change with a bounded, source-backed hypothesis;
3. a different interconnect/topology;
4. a new exact kernel design with a standalone critical-path result large
   enough to move the end-to-end record.

## Protected State

- Accepted source: `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`
- Accepted model:
  `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/Qwen3.6-27B-Q8_0.gguf`
- Promoted evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion`
- Pass-1 evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps`

Inspect source status and service/process ownership before using these paths.
Do not reset them, replace the accepted build, or delete raw evidence during a
new model bring-up.

## Main-Only Workflow

All repository updates belong directly on `main`. Use focused commits, source
patches, result packets, and external build/source directories for experiment
isolation. Do not create a Git branch or secondary worktree for a reopened Qwen
experiment.
