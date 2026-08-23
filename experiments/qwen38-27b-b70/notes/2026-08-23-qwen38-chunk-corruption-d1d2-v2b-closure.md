# Chunk-corruption D1/D2 v2b closure: both mechanisms dead

Date: 2026-08-23. Structured summary:
`../data/2026-08-23-qwen38-chunk-corruption-d1d2-v2b-closure.json`.

## Final outcome

The preregistered pair completed on the sealed isolated ext4 cache. D7 stayed
green; D4 reproduced the exact eighth-dose degeneration
`B70_QWEN3!!!!...`. Instrumentation therefore did not cure or move the dose
boundary.

D1 is dead. Across all eight D4 dose rows, each request allocated six blocks
in each of Mamba cache groups 0, 1, and 2 and later released those exact
eighteen blocks. There were no live-slot collisions and no slots left live at
trace end. Numeric block IDs advanced because the free queue did not cycle
back within eight requests, but there was no leak, premature reuse, or
wraparound collision.

D2 is dead. The native rank-0/layer-0 call site emitted sixteen `pre_native`
records: computed tokens alternated 0/1024, while `has_initial_state`
alternated false/true exactly for all eight requests. The eighth request was
not different before the native kernel consumed the flag.

The stricter post-run validator additionally requires exact allocation/free
set equality and an empty live-slot map. It passes the preserved one-row
probe, D7, and D4 traces without another GPU run.

## Safety and performance accounting

The isolated cache input/output manifest is byte-identical in D7 and D4:
`8ce2ed4646f6fa33563c20619d382e5d13b3a7b60e609b03230e968c608b55b3`.
The D4 driver independently ran its cache postflight despite the expected
quality return code 1. The recovered source cache verified unchanged after
every arm. No diagnostic throughput is promoted, and no historical
30.2/49.0/71.7/101.17 capture was edited or lowered.

After evidence capture, the two-file D1 patch was removed from the live vLLM
source tree and the tracked diff returned to the empty SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
This matters for speed safety: constructing D1 tensor summaries can
synchronize even before its writer checks the enable flag. Future benchmarks
therefore cannot inherit diagnostic overhead accidentally; the exact patch
remains preserved in Git for deliberate isolated-cache reuse only.

## What remains and what is next

The persistent-scratch dependency and exact dose-8 boundary still stand, as
do the earlier exclusions for scratch contents, pool tail, conv/SSM foreign
slots, allocation churn, and pointer reuse. The best-supported shape remains
a layout-coupled writer on the multi-chunk-prefill path that corrupts a stable
victim only when the persistent pool pins the arena.

This mechanism program is exhausted. The next program needs a fresh
preregistration. Ranked by information per run:

1. checksum live KV-cache pages and fixed positional/metadata buffers between
   dose requests to identify the first victim and exact dose;
2. place much larger head-side and interleaved canary brackets around the
   persistent arena (tens of MiB, not just the already-clean pool tail);
3. if neither localizes the write, build the exact native GDN/chunk-prefill
   shapes with device AddressSanitizer and run one capped dose-8 reproducer.

Long-context serving remains unsafe with persistent scratch enabled;
scratch-off is only a mitigation with its own 31/32 transient. The strict
short-context records and the closed 96-cell nightly matrix remain valid.
