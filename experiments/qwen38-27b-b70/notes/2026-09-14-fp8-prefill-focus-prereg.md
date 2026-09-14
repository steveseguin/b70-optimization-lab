# Final bounded FP8 prefill pass

User selected official Qwen3.8 27B FP8 as the preferred model and authorized one
modest follow-up before moving on. This is a measurement/profiling reproduction
of the published R304 runtime, not an upstream rebase or a broad optimization
campaign. Preserve all earlier frozen packets and unrelated four-card LTX work.

## Identity and inputs

One owned server on the two-B70 `steve-TURIND8-2L2T` host. Official FP8 revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, direct model manifest from the FP8
recipe, public R304 image
`sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
TP2, fixed MTP1, draft-only INT4 full-vocabulary head, FP16 activations/native
KV, whole-graph deterministic compile, XPU graph capture disabled, V1 runner,
one active sequence, prefix caching disabled. Capacity and batch budget are
both 4096 tokens; GPU utilization .95. This is a separate operating profile
from the earlier 1024-budget short-input test. Do not replace its homepage
number or infer a speedup across workloads/budgets.

Run [the single-stage controller](../scripts/run-fp8-prefill-focus.py) with
`--profile 27b-fp8 --profile-trace --port 18152 --out
/mnt/fast-ai/bench-results/qwen-fp8-prefill-focus-20260914/27b-fp8`.
The controller adapts the frozen previous baseline runner without modifying it.
It reuses the existing wire client and diagnostic profiler request.

The [corpus](../data/2026-09-14-fp8-prefill-corpus.json) contains unrepeated
contiguous prose, Python and setup-documentation excerpts. Tokenize without
special tokens and truncate numeric IDs to exactly 512 and 2048 tokens. Use
128 forced output tokens for timing, three repetitions per class/length in each
of baseline and final-control arms, separate warmups. Every request must have
zero cached tokens, complete numeric outputs and repeat parity. There are
18 measured requests per length across both arms. Aggregate median within each
class, median across three classes, then mean of the two arm aggregates.

Server prefill is input tokens divided by histogram duration from first
scheduled execution to first token. Require a single observation and correct
input-token delta. Record HTTP TTFT and 99-interval decode separately.
The 2048-row call may use a different oneDNN catalog entry: the fixed-K hook
covers at most 512 scheduled rows. Do not label the long point fixed-K or
assume identical performance scaling. Retain actual runtime/launch identity.

## Quality, profiling and stopping boundary

Run the complete 12-prompt natural-completion suite with 512 output cap and
objective canaries, requiring full output identity with the qualified R304
reference at `qwen38-fp8-rebase-v0290-rb1-20260913/mtp1-a/strict` under the raw
benchmark root. Preserve full copied references and hashes.

After the unprofiled baseline and quality gate, capture one 512-input/one-output
profiler request. Require its first token to match the unprofiled run, stop
profiling, and collect final unprofiled controls. Trace time is diagnostic and
excluded from published rates. No model instrumentation or runtime mutation.

The source audit found that FP8 activation quantization is already skipped,
scales are prepared once, weight transposes are views and oneDNN primitives are
cached. The earlier allocation screen was neutral on FP8. Scratchpad/descriptor
and geometry variants have closed negatives in the do-not-repeat index;
CLASSPAD or new batching arithmetic requires substantial separate qualification.
Do not rerun those candidates. Inspect the trace for a materially different
bottleneck, but do not force a patch or widen this task when none is supported.
This preregistration authorizes no candidate runtime arm. A single process can
supply measured baseline points and a diagnostic lead, not a promoted speed win.

Check Git/processes/listeners/render ownership, hold the exclusive prefill lock,
and pass both-card compute/XCCL health. Monitor new journal faults during startup
and requests. Any fault halts requests; preserve failures. One graceful shutdown
of the owned server, no restart/retry chain. No power, clocks, governor, ASPM,
swap, page-cache, driver-reset or reboot changes. Postflight both cards and journal.

Publish completed measurements and the bounded optimization conclusion with
raw/hash-bound evidence, suitable renderer/identity checks and live verification.
LocalMaxxing disposition is withheld: these are prefill baseline points, not a
new qualified decode record. End the prefill campaign after this pass.
