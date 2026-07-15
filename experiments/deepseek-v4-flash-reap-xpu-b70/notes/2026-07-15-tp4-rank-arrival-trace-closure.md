# TP4 rank-arrival trace closure

Date: **2026-07-15**

## Question

Could decode time be recovered by measuring per-boundary rank-arrival skew at
the 87 BF16 `[4096]` TP4 all-reduces, then overlapping useful work before the
slowest rank arrives? The integration gate was an adjusted cumulative skew of
at least `0.50 ms/token`. Raw clocks from different B70s were never compared;
each rank recorded only local elapsed ticks from entry until it saw epoch
markers from all four ranks.

## Diagnostic design

A default-off oneCCL experiment extended the existing 16-thread graph-recording
sequence kernel rather than adding another command. It allocated device-USM
records, calibrated `__spirv_ReadClockKHR(1)` against a profiled event, and
attempted to exchange epoch-tagged LL256 messages through the unused tail of
the IPC scatter buffer. The snapshot API copied records to host only after the
timed chain. The exact four-rank microgate retained the production ring, BF16
sum, count 4096, 87 calls, and changed inputs.

Experiment/revert history preserves the implementation:

- oneCCL `b6b6481` / revert `14db31d`;
- vLLM snapshot hook `fc03ca89f` / revert `8721e07b4`;
- the reusable exact gate is
  `../scripts/tp4-87-allreduce-recording-gate.py`.

## Bounded attempts and failure

The initial shared-USM allocation was not host-readable on this B70 runtime and
segfaulted during snapshot. Device USM plus explicit queue copies repaired the
snapshot path. The clock calibration was also corrected: the reported 52 ns
profiling resolution is not the device-clock period, which measured roughly
0.36-0.53 ns/tick and sometimes varied enough to fail the 2% repeatability
gate.

Seven subsequent marker variants all preserved exact all-reduce output, but
every recorded sample timed out with `timeout_mask=15`. This included the
rank's marker in its own local buffer, so the records cannot support any claim
about cross-rank skew. Explicit logical flag lanes, LL256 cache-controlled
loads/stores, a GPU-scope clean fence, and finally the production
`shuffleData` + `insertFlags` encoder did not repair visibility. The final
attempt recorded 87/87 timeouts on each of four ranks; rank 2 also had a 3.15%
clock-calibration disagreement. Its apparent `4.492 s/87` is diagnostic
timeout cost, not collective performance.

Raw evidence is under:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/arrival-skew-microgate-smoke-20260715T0900Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/arrival-skew-microgate-smoke2-20260715T0900Z` through `smoke8-20260715T0935Z`.

## Decision

Close this marker implementation without a full-model run. It failed before
the measurement gate, so there is no evidence that rank-arrival skew offers
`0.50 ms/token`, and no speed claim or LocalMaxxing submission is warranted.
Both runtime trees were explicitly reverted. Production continues to use the
venv oneCCL `libccl.so.1.0` SHA-256
`ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`.

The important negative result is methodological: same-device elapsed clocks
remain the correct way to measure skew, but a marker must first prove local and
peer visibility with negligible tax. Do not infer skew from distorted
cross-device profiler timestamps or from these timeout durations. A future
retry needs a dedicated, independently validated IPC marker allocation or a
native Level Zero timestamp/command-list trace; it must still clear the same
0.50 ms/token gate before touching the model server.
