# Goal 1 measurement foundation

Date: 2026-08-09

## Objective

Close the missing scorecard before optimizing the model: cold prompt
processing, TTFT, request wall time, conventional tokens 1--100, sustained
tokens 1--512, and honest c2 behavior at 4K-class, 17K, and near-32K context.
This is harness work and preregistration, not a throughput result.

## Fixed measurement definitions

- Primary decode: `99 / (t100 - t1)`, because 100 token events contain 99
  intervals.
- Sustained decode: `511 / (t512 - t1)`; token 512 itself must have a uniquely
  aligned SSE timestamp.
- A full-512 row requires exactly 512 replay tokens, stream/replay stop type
  `limit`, no truncation, native `cache_n=0`, exact prompt calibration, and
  exact stream/replay content and token alignment. `ignore_eos=true` is part of
  this performance identity. Natural-stop retrieval remains a separate quality
  gate.
- Every full-512 c1 packet ends with a fixed 128-token, slot-0 canary against
  the sealed DNN-off oracle. Its rendered prompt, token IDs, content, stop,
  cache, truncation, and returned-slot evidence must all match after the timed
  streams and deterministic replays have finished.
- c2 conventional aggregate decode:
  `1022 / (max(t512) - min(t1))`.
- c2 request-wall aggregate: 1,024 generated tokens divided by barrier release
  to the later request end.
- c2 aggregate prompt processing: the sum of both evaluated prompt-token
  counts divided by barrier release to the later first token. Each native
  prompt timing and each TTFT are retained as well.
- c2 send skew must be at most 25 ms; both token-100 timestamps must precede
  either token-512 timestamp.
- Both slots in both fresh c2 phases must also pass the fixed DNN-off 128-token
  external canary. This prevents a deterministic candidate regression or a
  slot-specific error from qualifying merely because its sequential and
  concurrent rows agree with each other.
- After timing, both selected-band prompts run as cache-zero, natural-stop
  retrieval checks. All five JSON fields must be exact, and each natural-stop
  token sequence before its terminal EOG token must be an exact prefix of its
  corresponding forced-512 row, and the forced content must begin with the
  natural-stop content. (`ignore_eos=true` deliberately chooses a different
  token at the EOG position.) The later retry therefore cannot mask a
  concurrent-only or forced-decode divergence. Natural-stop tokens/content
  must also match exactly across the two fresh phases by case ID.
- Non-perturbing `/metrics` snapshots immediately before and after the two
  timed streams require exactly 1,024 predicted tokens and at least 1.5
  predicted tokens per `llama_decode()` call. Prompt evaluation adds decode
  calls without adding predicted tokens, so this is a conservative direct
  generation-batching proof rather than a client-overlap inference alone.

## Workload and identity

The paired suite has two distinct, independently calibrated prompts in each
band. All six were regenerated with the pinned Qwen tokenizer and chat
template; declared and actual counts match exactly:

| Band | Prompt tokens | Prompt + 512 |
|---|---:|---:|
| 4K-class | 4,369 / 4,317 | 4,881 / 4,829 |
| middle | 17,274 / 17,171 | 17,786 / 17,683 |
| near-32K | 31,846 / 31,841 | 32,358 / 32,353 |

The retained calibration is
[`data/c2-suite-calibration-v1.json`](../data/c2-suite-calibration-v1.json).

The c1 Goal-1 baseline is locked to Q8_0 weights, F16/F16 KV, one slot,
32,768 context, DNN0/OPT1, graph off, VMM on, full offload, batch 1,024,
microbatch 128, and the recorded FA selectors. The realistic full-512 pass
must preserve the exact 128-token prefix from the sealed DNN-off oracle
(`e4477808...f5dbcc`).

The c2 baseline is the same model and selectors with total context 65,536,
two 32,768-token non-unified slots, continuous batching, 4,096 MiB F16 KV,
about 299 MiB recurrent state, `65/65` offload, and at least 1,024 MiB of
reported device headroom. Sequential per-slot oracles and concurrent timing
use separate fresh server starts. The concurrent phase may reverse the two
case-to-slot assignments without weakening token comparison.

## Integrity and safety

- All streamed work precedes deterministic replay work, so replay cannot warm
  later measured rows.
- Returned slot IDs, predicted counts, cache counts, truncation, stop type,
  full native timings, prompt hashes, token IDs, and content hashes are kept.
- JSON integers are type-strict: booleans cannot masquerade as token IDs, slot
  IDs, cache counts, predicted counts, or prompt counts.
- Failed, duplicate, extra, concurrent, or self-overwriting oracles are
  rejected. Inputs and output paths cannot collide.
- Both slots must be idle with 32,768-token capacity before and after each c2
  phase. No slot polling occurs inside official timing.
- Model, runtime, tokenizer, server argv/environment, allocation, offload,
  VRAM, host memory, cleanup, port closure, and device faults are fail-closed.
- The model is opened once under a shared lock, hashed through that pinned file
  descriptor, and loaded by every server phase through `/proc/self/fd`. Its
  inode/stat identity is checked throughout; official c1 and c2 evidence also
  rehashes the same descriptor after teardown. A pathname replacement or
  in-place mutation therefore cannot silently inherit the pinned model label.
- The runtime identity includes the executable, all eight co-located
  llama/ggml/mtmd shared objects, and every file-backed dependency resolved
  after the oneAPI environment is loaded. Those hashes and the dependency
  graph are rechecked across each lifecycle.
- Shared per-GPU and per-port leases prevent c1, c2, direct launcher, and
  four-card wave processes from claiming the same resource concurrently.
  Official isolated c1 and c2 hold all four GPU leases for the entire timing
  lifecycle; the functional four-card wave holds one card per child under an
  outer all-card lease.
- Server output is written directly by the tracked llama-server process. There
  is no asynchronous logger that can append after cleanup or artifact sealing.
- Harness inputs are hashed and rechecked around execution; external artifacts
  receive a verified manifest. A detached `completion-status.json` is the only
  authoritative PASS marker and is written atomically only after that manifest
  verifies; a pre-seal status file never claims PASS.
- The retained kernel journal must be captured successfully before its device
  fault scan can count as clear; an unreadable journal is a failed evidence
  gate, not an empty scan.
- No reboot or driver reset is authorized by this work. Use the passive-first
  recovery policy only if a confirmed device problem occurs.

## Four-GPU first wave

After offline review and a focused clean commit, use the four cards for a
parallel functional screen:

- GPU 0: c1 4K-class full-512 pair;
- GPU 1: c1 middle full-512 pair;
- GPU 2: c1 near-32K full-512 pair;
- GPU 3: c1 12-prompt realistic full-512 suite with sealed-prefix comparison.

Those simultaneous rates are diagnostic because cards can share CPU, storage,
power, and thermals. Follow with quiet isolated c1 and c2 measurements, then a
second-card reproduction. Optimization starts only after this baseline packet
is correctness-qualified.

The parallel wrapper is
[`scripts/run-goal1-four-gpu-wave.sh`](../scripts/run-goal1-four-gpu-wave.sh).
It preclaims all four GPU and port leases, uses bounded process-group teardown,
and seals both the four child packets and its aggregate functional-only packet.
Child completion markers explicitly say `parallel-functional-screen` and
`performance_promotable=false`; isolated measurements use a distinct evidence
class.

## Offline validation

The current foundation passes Python compilation, Ruff, shell syntax,
`git diff --check`, exact tokenizer calibration, and 41 unit tests covering
99/511 interval accounting, suppressed-SSE alignment, paired prompt loading,
baseline/prefix oracle mutation, exact c2 row/canary gates, barrier timing,
aggregate arithmetic, release skew, serial execution, decode occupancy,
reverse assignment, strict integer evidence, natural-stop semantic/prefix
linkage, independently recomputed prompt-rate consistency, external and
post-512 canary/PP gates, and output-path safety. The
runtime bundle verifier also passed a real 33-dependency capture/recheck and
rejected deliberately corrupted local-DSO and dependency-graph identities.
