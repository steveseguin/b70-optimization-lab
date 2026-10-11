# Fourth GPU incident closed — router padding contract defect

<!-- campaign-closeout -->

## Question and identity

**The fourth incident is closed as a software defect in the experimental
Screen 1b mmap-adapter line: router padding sentinels reached alignment code
that indexed them as expert IDs.** Neutralising the router padding mask before
alignment lets this TP4 line load and complete its startup profile under the
strict boundary, with zero violations, zero new kernel faults and clean exit.
This closes that defect; it does not finish the Flash-Next optimization lane.

Proof run, read-only source:
`/mnt/fast-ai/bench-results/flashnext-moe-boundary-window-20261011-router-padding-v5`.
Unit: `flashnext-screen1-20261011T012631`.
Boot: `13858eef-ec68-44ea-a67c-9444933b7100` (different from attempt 8).
The [receipt summary and original-file hashes](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/summary.json)
pin this one run, not a rerun performed for this report.

Official FP8 revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, TP4/EP4,
MTP1, full 16-bit-family KV, attempt-6 placement, 64 profile tokens, context
4,352 and 376,569,856 KV bytes/rank are retained. Image:
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`;
vLLM 0.30.0+xpu, Torch 2.13.0+xpu, Triton 3.7.2+xpu,
vllm-xpu-kernels 0.1.14.1. Applied diagnostic manifest:
`2879f61968e86a79d13cbfdf3e14fdc951805cb87482878832c8a97937a510cb`.
The load guard is 96 GB; exact large pinned allocations and the per-process
`NEOReadDebugKeys=1 EnableDeferBacking=0` settings match the experimental line.
This is **not the certified A367 recipe** or its host allocation path.

## Outcome

### Timeline (October 11, UTC)

| Time | Event and evidence |
| --- | --- |
| 00:45:38–00:56:45 | Attempt 8 hashes the official model and finishes loading all four ranks. |
| **00:56:50** | Fourth GPU incident at the first MoE startup profile/dummy forward inside KV initialization, before readiness or graph capture. CCS faults precede recorded controller stop and crash reports; container later exits 1. [Original chronology](2026-10-11-attempt8-fourth-incident.md). |
| After attempt 8 | [CPU source/ownership audit](2026-10-11-attempt8-moe-first-forward-audit.md) prioritises production routing/alignment/workspace writes. The passing one-rank probe used hand-built valid IDs and never exercised the production router. Dummy profiling skipped the mmap-PLE row-fetch hook. |
| 04:00:23 | Diagnostic plumbing failure 1: graph mode NONE conflicts with the predictor's required compilation NONE / FULL_DECODE_ONLY identity. Restore attempt 8's flags; retain the diagnostic's explicit capture bypass. |
| 04:08:41 | Plumbing failure 2: staged path resolution looks for the placement census below bench-results. Resolve repository inputs through the explicit source checkout. [Both repairs](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md). |
| 04:27–04:38 | Plumbing failure 3: source-paths-v3 controller cancels before MoE; cleanup replaces its original exception with the exit error. All 1,101 allocation receipts pass, no new GPU fault. Preserve the first exception before cleanup in v4; the original cancellation trigger remains unrecoverable. [Audit](2026-10-11-moe-boundary-run1-cancelled.md). |
| **05:11:16** | v4 catches all **640 signed int32 IDs = -1** in each rank's raw `[64,10]` router tensor. Strict range check stops before alignment, without new kernel faults. [Catch and source trace](2026-10-11-moe-boundary-caught-router-ids.md). |
| Before 05:26:31 | Production router-padding compatibility fix applied; diagnostic package resealed with unchanged strict checks. Source-bound CPU suite records 143 passes. |
| 05:26:31 / 05:28:52.550 | v5 controller starts / proof container starts. Zero generation requests declared and recorded. |
| **05:46:28.482–05:46:29.065** | All ranks finish profile synchronization and record `profile_only_no_warmup`; API startup follows at/after 05:46:37 in the server log. Each rank has 15,895 boundary receipts, no failed check. |
| About 05:46:45.233 | Sample 2,148, in the ready plateau, records the whole-run host-pressure maximum: 77.079 GB. UTC is derived from paired boundary wall/monotonic clocks. |
| 05:47:03 approximately / 05:47:15.596 | Controller sends SIGINT for `controller completion` (command rc 0); container exits **0**, not OOM-killed. All four teardown receipts pass. |
| 05:52:23 | Watcher completes the 305-second post-exit gap, clear. |
| 05:52:25 | Controller unit exits **2**, correctly refusing MTP1 qualification because all four VRAM reserves remain unknown. This is separate from the clean container exit. |

### What the proof establishes

The fixed experimental TP4 line completed loading, the 64-token target/MTP
profiling path and a 20.685-second ready plateau, then stopped cleanly.
Each rank has **15,895 receipts**, including **12,427 explicit passing checks**,
49 checked alignment passes, 98 synchronized GEMM completions and one
synchronized profile completion: **63,580 receipts total, zero failed checks**.
The remaining receipt rows are events, not additional assertions.

`calibration-load.json` records `ready=true`, `clean_exit=true`,
`watchdog_reason=null`, `failure=null`, `cleanup_failure=null` and
`generation_requests=0`. `graceful-stop.json` records SIGINT, rc 0 and
`controller completion`; `container-exit.json` records ExitCode 0.
The completed watcher and kernel-window recount show **zero new fault-class
lines**. The four `kernel-*.log` files are full-boot snapshots and contain seven
older matching lines before this window; do not describe the whole files as
fault-free. The coordinator also reported zero faults in its independent
watch; that separate raw watch was not supplied to this review.

The calibration's overall **`verdict.passed=false`** remains intact: the only
listed refusals are unknown VRAM reserve on ranks 0–3. The unit journal's
`REFUSED/STOPPED: Load measured; MTP1 still refused` is not a failed profile or
a new incident. No automatic admission or floor revision follows from closure.

## What worked

V2's dummy batch marks every row as padding. Native top-k writes `-1` for
those rows. The pinned general aligner rejects IDs >=512 but omits the negative
check, so its count/sort steps can index before their buffers, including
`cumsum_buffer[-1]`, and use the resulting value as a write index. All four
raw tensor hashes match 2,560 bytes of `0xff`; the bad IDs precede remapping.
The observed input, concrete invalid-write mechanism and corrected complete
profile together support closing the fourth incident as this software defect.
The historical faulting instruction/address-to-allocation match was not saved;
closure does not manufacture one or explain every earlier GPU incident.

The [production fix](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-router-padding/README.md)
returns `None` from ordinary and bias router padding-mask helpers only for
Screen 1b on XPU. Padded rows use ordinary routing before alignment; no ID is
clamped to expert zero and no boundary check is relaxed. Valid rows retain the
same routing arithmetic. The older lab runtime already had a
[negative-ID native guard](../patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0004-fix-moe-ignore-padding-sentinels-during-alignment.patch);
that retained lab fix was missing in the modern wheel, not superseded by it.

## What failed or remains uncertain

This is **one instrumented startup run, with no generation requests**. Warmup
and graph capture were explicitly bypassed; subsequent model execution was
blocked by the diagnostic. It does not qualify generation, mmap-PLE row fetches
on real prompts, captured execution, long context, concurrency, speed, exact
full-model output parity or fresh-process repeatability. Boundary checks cover
indices, spans and ownership metadata, not every native USM mapping/lifetime.
Extra synchronization changes scheduling. The native aligner remains unsafe
for arbitrary negative IDs supplied by other callers.

### Remaining open questions for the lane

1. Does a bounded real-prompt generation screen pass with the strict boundary
   retained, including the PLE fetch and MTP paths? Prepare a separately sealed
   generation-capable diagnostic; the v5 load-only hook refuses further forwards.
2. Do generated tokens match the registered same-identity oracle exactly, with
   deterministic repeats and a fresh-process repeat? The valid-row identity
   argument and dummy profile are not that quality gate.
3. What are each card's measured peak/free VRAM reserves and this line's host
   demand during generation? Resolve calibration's missing VRAM observations;
   one sampled load/plateau peak is not a serving bound.
4. What does the **certified A367 recipe** need on this host? Its separate
   load-only calibration requires the owner's approved admission floor (or
   explicitly scoped calibration exception), matched runtime evidence and
   resolution of the historical model-receipt mismatch; this run supplies none
   of those approvals or substitutions.
5. Can the retained native negative-ID guard be ported and qualified on the
   modern wheel, and can the fixed path pass without diagnostic synchronization?
   Graph/capture, longer-context and representative performance gates remain
   separate later work; the certified **46.854250 tok/s** record is unchanged.
6. The v3 controller's lost initiating exception and attempt 8's exact faulting
   instruction remain unavailable historical evidence. Revisit only if new
   evidence appears or the refusal recurs with first-cause retention; do not
   repeat the unmodified failing stage to recover what was never saved.

## Evidence and patches

- [Proof summary, source hashes and extracted memory/rank counts](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/summary.json).
- [Original calibration receipt copy](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/calibration-load.json), [container exit](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/container-exit.json), [watcher](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/watcher.json) and [controller journal](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-closed-20261011/controller-journal.log).
- [Memory admission appendix](../experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md#measured-on-the-fixed-line-2026-10-11-053x-utc): post-hash availability **119.170 GB**, trough **47.100 GB**, peak pressure **77.079 GB**, availability decline **72.070 GB**; attempt 8's incomplete-startup peak was **75.448 GB**.
- [Boundary source, patch, seals and plumbing history](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md); [router catch and source-bound CPU validation](2026-10-11-moe-boundary-caught-router-ids.md).

The summary pins full raw source files retained read-only at the proof path;
small decisive receipts and journal are copied into Git. Nothing was removed
from the raw run. Verification independently recounts JSONL, checks its hash
against calibration, recomputes phase extrema and per-rank inventories, and
filters kernel lines by the saved cutoff. This review used CPU only, nice 19,
`OMP_NUM_THREADS=2`; only the requested journal was read. No GPU/device,
server, Docker start/run, service operation, endpoint, power or memory setting
was touched. No scratch was created.

## When to revisit

The next lane step is a **bounded generation screen under the boundary** after
its own current coordinator admission, followed by the **certified-recipe
calibration when the owner approves its floor**. Closure is not a new launch
permission and does not reopen any other incident or LTX window. Keep the
original fault markers, acceptance receipts, failed stages and patches intact.
