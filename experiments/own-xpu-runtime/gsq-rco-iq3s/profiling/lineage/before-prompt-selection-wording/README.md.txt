# Fixed prompt 00 class diagnostic

This preparation runs no device work. Root owns the operational plan and launch.
The additive launcher reuses the frozen native binary and privately imported
[serving adapter](../serving/adapter.py); its only native command change is
`--timing token` to `--timing class`. The model, full vocabulary, draft allocation,
rank placement, split 24, context 4096, arithmetic and state handling stay identical.
The [first-run monitor](../operating/model_once.py) provides the unchanged physical
holder, fault, memory, queue, one-stop and retained-owner behavior.

Admission requires the completed, clean all-12 baseline terminal and hash-bound
full result, matching native binary, original prompt tokens and frozen reviewed
sources. Prompt 00 is fixed before examining its timing. The sequence uses one
pair of owners: full RESET, the existing disjoint target-only warmup (8 outputs,
EOS disabled), full RESET, then prompt 00 target-only with cap 128 and original
EOS policy. Every output token and both complete target-state maps must equal
the unprofiled baseline arm. No MTP performance measurement occurs here; its
allocation is retained to preserve the baseline identity.

There are two requests and three retained state dumps including the initial
blank state: 761,436,364 bytes including a 64 MiB metadata allowance. Root cache
forecast is 128 MiB above the 27 GB floor; external reserve is 2 GiB. These are
monitored forecasts, not quotas. Nothing is pruned. The fixed control parent is
`/home/steve/own-xpu-runtime-results/gsq-profile-a.control`; evidence is
`/mnt/usb-models/own-xpu-runtime-results/gsq-profile-a`; unit is
`gsq-profile-a.service`. Root creates the private control parent. Read-only
`python3 once.py --plan` refuses until all prerequisites and fresh paths exist;
`python3 once.py --run PLAN` requires the exact reviewed plan and safe unit.

The native request reset dumps the preceding `class-times.json`, then clears
class totals and reopens request streams. Final FINISH writes the measured class
report. Reports sum individual event execution durations across layers and the
whole request, including prefill; they are not decode-only kernel timings.
Per-half host enqueue-family counters reset each half, but their inherited names
(for example `dense_r5`) do not identify the GSQ kernel selected now. Likewise
the inherited aggregate GEMV/non-GEMV split mislabels the old generic fallback;
use the actual class labels. Driver copy work is not a complete per-class census.

Class mode enables event collection/queries at existing drain boundaries and
the rank 1 profiling queue property; rank 0 already has that property. Profiling
overhead and queue configuration differ from the performance baseline. Tokens
and final state are the instrumentation equivalence test. No speed or measured
bottleneck claim is made. `--record` is deliberately absent: it is an inherited
plan-only path, not a profiling option. The narrower `attribution` mode samples
only fixture positions 9–16 and routed labels, so is not used here.

The three small CPU tests check exact argv delta and frozen source refusal; they
do not launch owners. The wrapper reuses the reviewed baseline coordinator's
control flow but writes only the compact profile-result path/hash in terminal
evidence. Full result and class reports remain on USB.
