# Qwen3.6 Research Map

Use this page as the Qwen3.6 family front door. Qwen3.6 results in this
repository use different model sizes, quantizations, runtimes, hardware counts,
speculation modes, prompt suites, and accounting conventions. They are related
research lanes, not interchangeable benchmark rows.

Live service and active-lane authority remains [`CURRENT.md`](../CURRENT.md).

## Current Decision

Qwen3.6 27B AutoRound INT4 TP2 is paused after the final approved gate. The
dependency screen failed at 15/25 exact and `96.386 tok/s`. A later fixed
per-row RMSNorm screen matched both then-sealed four-prompt controls at
`106.663 tok/s`,
but its matched-source 25-prompt candidate was only 12/25 exact at
`93.445681 tok/s`. The approach failed both normal gates, is not
production-ready, and no LocalMaxxing row was submitted. The distinct Q8
target-only TP2 lane remains closed and banked at **`35.699225 tok/s`**
conventional.

Start with:

1. [Q8 TP2 handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md)
2. [promoted Q8 TP2 result](../results/qwen36-27b-q8-tp2-asrock-b70/README.md)
3. [standalone Q8 TP2 repro](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
4. [Q8 TP2 source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
5. [post-record pass-1 ledger](../notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md)

Do not retry the built-in TP2 SYCL profiler or the unsafe root-both remote-write
prototype; both caused device faults/resets. The other pass-1 hypotheses were
neutral or slower and remain default-off/reverted.

## Qwen3.6 Lane Catalog

| Identity | Hardware and runtime | Verified status | Primary pointer |
| --- | --- | --- | --- |
| 27B GGUF Q8_0, target-only | 2x ASRock B70, llama.cpp/SYCL TP2 | Current no-speculation record: `35.699225 tok/s` conventional; 12/12 exact, cache-zero; closed after pass 1 | [handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md) |
| 27B GGUF Q8_0, target-only baseline | 1x B70, llama.cpp/SYCL | `15.550257 tok/s` 128-token median; exact 32K F16-KV retrieval baseline; service/concurrency experiments are separate evidence | [experiment lane](../experiments/qwen36-27b-q8-gguf-b70/README.md) |
| 27B AutoRound INT4, MTP3 | 2x B70, vLLM/XPU TP2 | Paused/failed gate: RMSNorm four-prompt canary matched then-sealed controls at `106.663`; final matched-source 25-prompt candidate 12/25 at `93.446` | [final closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md), [structured summary](../data/qwen36-27b-autoround-int4-batch-invariant-rmsnorm-closeout-20260817.json), and [prior dependency closeout](../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md) |
| 27B AutoRound INT4, target-verified MTP | 1x B70, vLLM/XPU | Historical high `68.236263 tok/s`; later isolated confirmation was `65.4-66.7` | [result packet](../results/qwen36-27b-autoround-int4-b70/README.md) |
| 27B GGUF Q4_0, DFlash5 | 1x B70, llama.cpp/SYCL | Closed strict record `47.818818 tok/s` historical (`47.340630` conventional); unchanged Q4 target verifies accepted tokens | [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md) |
| 27B GGUF UD-Q4_K_XL, intrinsic MTP | 1x B70, llama.cpp/SYCL | Best valid p-min support row `31.480049 tok/s`; different target/quality identity | [result packet](../results/qwen36-27b-mtp-gguf-q4-b70/README.md) |
| 27B native FP8 | 2x B70, vLLM/XPU | Community validation `30.171 tok/s` on a different prompt-length benchmark; not rank-comparable to fixed-suite rows | [status](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) |
| 35B A3B Quark W8A8 INT8 | 4x B70, vLLM/XPU | Closed reference; strict PIECEWISE forced-comm baseline about `93.55 tok/s`; no valid `>150` speculative result | [result packet](../results/qwen36-35b-quark-int8-b70/README.md) |

The repository [Qwen3.6 27B model board](../README.md#qwen36-27b-model-board)
contains the full row-by-row comparison and accounting labels.

## Identity Rules

Before comparing Qwen rows, match at least:

- exact model repository, revision, file hash, and quantization;
- target-only versus DFlash/MTP/other target-verified speculation;
- llama.cpp versus vLLM/XPU and exact source/runtime commits;
- TP/PP/concurrency and B70 count/topology;
- graph mode and compilation configuration;
- KV precision, context, batch/ubatch, cache/reuse policy, and sampler;
- prompt suite, completion length, freshness, and throughput accounting.

For the 35B Quark lane, a missing
`COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` changes the run into the
slow graph-none identity. Never interpret that mismatch as a regression.

Compressed, speculative, and target-only rows may all be valid, but they must
retain their declared identities. Do not promote a family-level “Qwen speed”
number without those boundaries.

## Current Q8 TP2 Closeout

The post-record pass tested collective topology, queue readiness, Q8 scheduling,
Level Zero submission, copy offload, host polling, thread/affinity controls,
FlashAttention variants, recurrent/GDN fusions, and power/clock hypotheses.
None cleared a matched promotion gate. The accepted source and reproduction
remain the recovery reference.

Reopen that exact lane only for a materially new input:

- a new checkpoint/quantization with its own quality baseline;
- an upstream SYCL/oneDNN/runtime change with a bounded source-backed thesis;
- a different interconnect/topology;
- an exact kernel proof with enough isolated critical-path value to move the
  end-to-end record.

Do not restart it with another generic flag sweep.

## Other Lane Decisions

### 27B INT4 AutoRound

The graph-safe FlashAttention and ReplaySSM transaction lane is a closed
reference. Its standalone repro now preserves the exact local-only vLLM and
XPU-kernel source, original run directories, pinned oneCCL/libccl dependency,
and historical target-verification rules.

The 2026-08-15 independent review remains the stronger historical
classification of the restored implementation.
It used six fresh starts, both physical GPU pairs, target-only controls, four
speculative repeats, and 25 cache-zero cold prompts. The speculative arms had
a `98.766 tok/s` central combined estimate, but every arm diverged from its
target-only control on 25/25 prompts and same-pair restarts diverged on 19/25
and 21/25. That is a real throughput reproduction, not a strict validation
pass or a robust `>100` result. No replacement LocalMaxxing row was submitted.

This is an AutoRound INT4/vLLM identity and must not be merged with the Q8_0
GGUF/llama.cpp record merely because both use a Qwen3.6 27B base model.

The subsequent native-packed/persistent-scratch recovery and current Inductor-
partition recovery are separate experiment identities. The partitioned arm
fixes the old recurring token-68 canary and raises the four-arm central median
to `99.798 tok/s`, but complete 512-token outputs still differ from target on
11–12/25 prompts. A lone `100.003 tok/s` arm is not a valid record and was not
submitted.

The 2026-08-17 dependency bisection is another distinct diagnostic identity.
Its final warmed four-prompt run is 4/4 exact at `110.675 tok/s`, but raw
controls contradict one another and the matched final-source 25-prompt gate
failed at 15/25 and `96.386 tok/s`. The all-INT4 correction also failed.
Preserve it as a negative patch packet; do not present it as the replacement
record.

The final batch-invariant RMSNorm follow-up is also nonpromotable. Stateless
and live W4/GDN controls excluded those focused operators, while serial and
fixed-geometry RMSNorm restored one near-tie. That causal repair matched both
then-sealed four-prompt controls at `106.663 tok/s`, then failed the matched
normal gate at 12/25 exact and
`93.445681 tok/s`. Preserve the complete source/config packet, but do not call
its focused RMSNorm delta a production patch.

### 27B Q4/DFlash And Intrinsic MTP

The DFlash campaign closed below its `100/200 tok/s` objectives. Read the
[closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md) before reusing its
kernel, graph, packing, or proposal work. Intrinsic-MTP and DFlash rows remain
separate from target-only Q8 and AutoRound INT4 rows.

### 35B Quark INT8

This is an archive/reference lane. Future work needs a controlled upstream
runtime/kernel bakeoff or graph-compatible speculative-state design, not ad hoc
flags. Read the [validity gates](../results/qwen36-35b-quark-int8-b70/validity-gates.md)
before comparing any result.

## Artifact And Storage Pointers

- [Qwen ignored-artifact archive manifest](../notes/2026-08-14-qwen-artifact-archive.md)
- [Q8 TP2 promoted data](../data/qwen36-q8-tp2-asrock-b70-20260813/summary.json)
- [Q8 one-card experiment](../experiments/qwen36-27b-q8-gguf-b70/README.md)
- [INT4 AutoRound experiment](../experiments/qwen36-27b-autoround-int4-b70/README.md)
- [graph-safe FlashAttention experiment](../experiments/qwen27_graphsafe_flash_attention/README.md)
- [Q4/DFlash experiment](../experiments/qwen27-dflash-sycl-b70/README.md)
- [35B Quark packet](../results/qwen36-35b-quark-int8-b70/README.md)

Tracked notes, patches, configs, and results stay in place. Large ignored build,
dependency, and diagnostic files may be archived externally only after their
recorded hashes and restore path verify.

## Main-Only Workflow

All repository changes go directly to `main` as focused commits. Use source
patches, external build directories, reproducible configs, and result packets
for isolation. Never create a feature branch or secondary worktree for Qwen
research.
