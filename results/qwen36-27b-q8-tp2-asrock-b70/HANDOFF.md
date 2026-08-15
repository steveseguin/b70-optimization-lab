# Qwen3.6 27B Q8 TP2 Handoff

Status: **active target-only optimization on 2026-08-15**

## Resume Bookmark

The accepted target-only two-B70 result is:

| Field | Accepted value |
| --- | --- |
| Conventional 99-interval median | **`36.604128 tok/s`** |
| Historical helper | `36.973866 tok/s` |
| Full-512 after-TTFT median | `36.533899 tok/s` |
| Quality | 12/12 cold 512-token outputs byte-exact to the accepted control |
| Cache | `cached_tokens=0` for 12/12 |
| Target | Qwen3.6 27B GGUF Q8_0 |
| Runtime mode | target-only TP2; no MTP, DFlash, draft, or reuse |
| Source base | mndodd llama.cpp `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` |
| Complete decoded patch SHA-256 | `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998` |

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
suite. It also records the exact SIMD16 Q/K RMS+scale+IMRoPE fusion and the
recurrent conv+SiLU+paired Q/K-L2 fusion. The current record adds two-chain
DP4A instruction-level parallelism to the reordered-Q8 kernel: `+0.707%`
conventional and `+0.464%` full-512 over the preceding promoted result, with
12/12 complete hashes exact. The pass-2 ledger also retains every rejected
faster-but-inexact form and the invalid stale-object DP4A screen.

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
- four independent reordered-Q8 DP4A accumulators versus the promoted
  two-chain form;
- power, clock, and scheduler explanations.

The built-in TP2 SYCL profiler and the root-both remote-write prototype caused
device faults/resets. Do not retry them. Other doors were neutral or slower and
remain default-off/reverted.

## Remaining Gap

Long direct repeats remain around the `36.6 tok/s` class, while the rough Q8 HBM
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

## Latest Promoted Experiment

The 2026-08-15 DP4A instruction-level-parallelism experiment is complete and
promoted. It splits each reordered-Q8 block's four dependent integer DP4A
operations into two independent accumulator chains, adds those integer
partials, and retains the existing FP32 scale and accumulation boundary. This
exposes instruction-level parallelism without changing the integer dot
product or the per-block FP32 order. The full endpoint reached `36.604128 tok/s`
conventional (`+0.707%`), improved full-512 after-TTFT by `+0.464%`, and
matched all 12 accepted output hashes with every cache count zero. The
isolated source is now the accepted source at
`/mnt/fast-ai/src/llama.cpp-q8-tp2-dp4a2`.

## Latest Closed Follow-up

The four-independent-accumulator DP4A follow-up is closed as performance-null.
Its valid fresh build had a distinct `mmvq.cpp.o` and passed the bounded TP2
mechanism/verification smoke, but a position-balanced `p64/n256/r3` A-B-B-A
screen measured `37.330746 tok/s` candidate versus `37.311496` promoted
control, only `+0.052%`. The candidate followed the host's slow/fast process
state rather than producing a repeatable gain, so it did not receive an
endpoint run. The accepted two-chain source and result remain unchanged.

## Active Coordination Checkpoint

As of 2026-08-15, one isolated exact-quality code-generation probe is in
progress: retain two DP4A accumulator chains but pair adjacent packed words
(`0->1` and `2->3`) instead of the promoted striped pairing (`0->2` and
`1->3`). Integer and FP32 boundaries remain unchanged. The first gate is the
compiled `mmvq.cpp.o`: if Intel's compiler canonicalizes both forms to the
same object, no GPU run will be claimed. The planned isolated source is
`/mnt/fast-ai/src/llama.cpp-q8-tp2-dp4a-adj`; do not duplicate this probe
without checking the latest `origin/main` checkpoint.

## Protected State

- Accepted source: `/mnt/fast-ai/src/llama.cpp-q8-tp2-dp4a2`
- Prior control source: `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`
- Accepted model:
  `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/Qwen3.6-27B-Q8_0.gguf`
- Prior promoted evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion`
- Pass-1/pass-2 and current promoted evidence:
  `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260815-dp4a2`

Inspect source status and service/process ownership before using these paths.
Do not reset them, replace the accepted build, or delete raw evidence during a
new model bring-up.

## Main-Only Workflow

All repository updates belong directly on `main`. Use focused commits, source
patches, result packets, and external build/source directories for experiment
isolation. Do not create a Git branch or secondary worktree for a reopened Qwen
experiment.
