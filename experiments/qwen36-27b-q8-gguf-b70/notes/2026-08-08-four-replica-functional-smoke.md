# Four simultaneous Qwen3.6 27B Q8_0 replicas pass

Date: 2026-08-08 local (`20260809T011029Z` run stamp)

Status: **PASS — functional topology only, not a promoted throughput result**

## Purpose

The selected deployment direction uses four independent llama.cpp processes,
one per B70. This smoke tested that all four target-only Q8_0 replicas can be
resident and generate concurrently without changing the validated model,
runtime, DNN-off selector, 4K F16-KV identity, or deterministic output.

Run directory:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-four-replica-smoke-20260809T011029Z`

The run first verified the pinned model, runtime, and prior DNN-off oracle
hashes. GPU0 then matched a one-prompt subset of that sealed oracle before its
fresh result became the common cross-replica oracle. Finally, all four cards
executed the same 128-token streaming plus deterministic replay request at the
same time.

## Result

- four distinct physical Arc Pro B70 ordinals, BDFs, and UUIDs passed the
  discovery gate;
- every process reported full `65/65` layer offload;
- every card retained `26,573 MiB` while all four services were resident;
- GPU0 matched the previously sealed DNN-off baseline;
- all four simultaneous rows passed intrinsic stream/replay validation and
  `PASS_ORACLE_EXACT`;
- every row produced token-list SHA-256
  `e6480d7ef60af9764f6dacb1ff1a37bacdf6dffe8b34c33d1790aed9e46fe769`;
- cache-reuse counts were zero, responses were not truncated, and each complete
  replay contained 128 tokens;
- diagnostic per-card token-1-to-100 rates ranged from about 15.520 to
  15.537 tok/s during the simultaneous request;
- all four processes exited without forced kill, ports 19460--19463 closed,
  every card returned from 26,573 MiB to 43 MiB, and both device/server error
  scans were empty;
- host `MemAvailable` was at least 124,090,652 KiB at every recorded checkpoint,
  and swap was unchanged.

The complete external packet is sealed by its own `artifacts.sha256`; that
manifest hashes to
`ec294eb5d456f5680aea902c66d17648fa0a74a3929cf7c604a326a4cbcada81`.

## Interpretation

The desired four-process topology is validated. It provides four independent
cluster-wide requests at `np=1` and is suitable for parallel functional and
optimization lanes.

This run does not validate 32K on all cards simultaneously, multiple server
slots per process, or aggregate production throughput. Its rates are not an
official score because GPU0 first created the fresh common oracle after matching
the already sealed baseline, all cards shared host and power resources, and
only one prompt was measured.
Official candidate timing remains isolated one-card work unless explicitly
preregistered as aggregate multi-service throughput.
