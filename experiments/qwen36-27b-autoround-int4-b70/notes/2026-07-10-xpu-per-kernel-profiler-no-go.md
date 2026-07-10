# Qwen27 XPU per-kernel profiler integration: no go

Date: 2026-07-10

Status: profiler/tooling diagnostic closed; no model timing result and no
LocalMaxxing submission.

## Goal

Obtain true device-kernel timing for the current graph-replayed `68.236 tok/s`
Qwen27 recipe before choosing a SYCL optimization target.

## Tools and attempts

Intel VTune 2025 was installed briefly, but GPU Hotspots applicability rejected
this host because its CPU is AMD. VTune and its profiling services were removed
immediately; no persistent system package or service change remains.

Intel PTI `unitrace` was then built from source:

```text
source: /home/steve/src/pti-gpu
commit: a5bab309f4ffdd78bd127035c46f5f75371160f8
unitrace: 2.4.0
build: Level Zero enabled; OpenCL/ITT/XPTI/MPI/OMP disabled
```

A small XPU GEMM smoke passed and produced valid `device_timing.txt` and
`device_submission.txt`, proving the installation itself works. The real vLLM
endpoint failed for two independent reasons:

1. Online server wrapping followed the API process but never flushed a timing
   file for the spawned `VLLM::EngineCore`. Setting
   `VLLM_ENABLE_V1_MULTIPROCESSING=0` did not remove that online EngineCore
   process boundary.
2. Offline `LLM` mode did keep model execution in the wrapped process, but
   graph replay contains so many kernel events that both
   device+submission timing and device-only timing failed to finish eight
   generated tokens after more than 15 minutes. Native decode is about
   `68 tok/s`; the tracing overhead is therefore several orders of magnitude.

Representative failed artifact roots are retained outside Git:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-unitrace-20260710T003634Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-unitrace-20260710T004901Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-unitrace-offline-20260710T005530Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles/qwen27-current-recipe-unitrace-offline-20260710T011125Z
```

None produced a completed EngineCore device summary. Do not infer kernel cost
from their profiled wall time.

## Decision

Do not retry per-kernel event tracing on this captured graph. Use the retained
scripts only as tooling reference:

```text
experiments/qwen36-27b-autoround-int4-b70/scripts/profile-current-recipe-unitrace.sh
experiments/qwen36-27b-autoround-int4-b70/scripts/profile-current-recipe-unitrace-driver.py
```

The active replacement is intrusive but bounded aggregate region timing with
graph disabled for diagnosis. It synchronizes whole target-layer categories
(`linear_attention`, `full_attention`, `mlp`) rather than every device kernel,
then returns to the graph-on recipe for any endpoint experiment.

The completed replacement measurements and their limitations are recorded in
`2026-07-10-current-recipe-target-region-profile.md` and the compact data file
`data/qwen36-27b-autoround-int4-b70-profiles/qwen27-current-recipe-target-region-profile-20260710.json`.
