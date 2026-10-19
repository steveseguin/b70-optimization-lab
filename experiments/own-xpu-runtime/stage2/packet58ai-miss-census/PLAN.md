# Preregistered census

Question: how much original tile16 expert service is exposed to pinned-host
misses, and what post-router time windows could a demand transfer use?

Identity: packet58ad's official/accepted quantized lane, iq3-p49-split32-v1,
one B70, HC p60fusion, 21,552,729,600-byte cache, overlapped cache maintenance,
zero-copy misses, full BF16 KV and context 4096. Record anchor: 30.396 tok/s.
The packet58ad WS128 tokens and acceptance metadata are copied and hash-bound
under lineage/record-chain-outputs.json. Accepted speculative tokens do not
exist on this target-only line; every generated token must agree exactly.

One load, five views, 12 fixed prompts × 128 tokens in each view. A0/A1/A2
have no profiling; B0 measures the unchanged mixed launches; B1 partitions
resident/miss work without changing its arithmetic. K1a/K1b precede the load.
Both warm controls expose instrumentation overhead; A0 remains exact but is
excluded from warm overhead comparisons. All request state resets remain,
with cached_tokens=0. These repeated views are diagnostic, never a cold-suite
performance claim. Expected job duration ≤1800 s; model-window cooperative
watchdog 7200 s (four times that expectation), with independent K1 watchdogs
and 90-second drain gaps. Cleanup may extend beyond a deadline; no hard kill.

At every input and output position, record all 48 layers, hit/miss expert IDs,
counts and logical requested bytes. Retain router completion and expert event
start/end timestamps. B0 measures the real router-to-first-expert gap. B1
measures resident and pinned-host partitions, including their arithmetic;
empty partitions are separately counted and excluded from useful service.
Resident service before a waiting miss partition is a potential transfer
window under that diagnostic ordering. Actual concurrent expert compute is
zero on this in-order queue. No claim is made to observe original-kernel
internal memory stalls. Different per-view cache demand is reported.

For each decoded token, sum the original B0 duration of entire expert launches
in layers with a miss. This deliberately erases even resident arithmetic,
so it is a generous ceiling on removable expert-kernel service, not a forecast.
Do not add the router gap to that saving. Report the split miss-service
ceiling separately; never subtract it from a differently scheduled control.
The primary conversion uses generated positions 2..100, corresponding to the
99 conventional inter-token intervals, and 1000/30.396 ms per token. Keep all
other measured token distributions and per-layer summaries.

Decision: ceiling ≥1.0 ms/token produces a bounded transfer brief; <0.670
closes rank 4 under this measured ceiling; the middle region calls for tighter
measurement. A B0 overhead above 2% in magnitude against either warm control,
or warm-control drift above 3%, blocks the decision. Report those values
rather than subtracting an assumed overhead. The 0.670 threshold gives about
2.08% on 30.396; it is slightly more conservative than exact +2% arithmetic.
Never reuse packet125's older pipeline gain or packet147's cross-identity proxy.

A future transfer design must account for learning the router IDs, submissions,
copy completion, the unchanged expert computation, safe pointer publication,
staging allocation and cache effects. GPU route output is not automatically
available to a host copy submitter. Exact tokens, deterministic repeats and a
fresh-server speed comparison are separate prerequisites to any optimization.

Preparation is CPU-only. Model/full-shape reads are forbidden while the
one-card hold is active. Existing allocation and post-load proofs are reused
by hash because the instrumented path allocates no additional device buffers;
the new 16 MiB host log buffer fits the existing 32 MiB metadata allowance.
Small native partition and reset tests cover the new code. The inherited
allocation proof is not represented as a newly executed full-shape test.

Packet58aid admission amendment: run the fresh d-smoke before the separate
five-view proposal. Both share this unchanged binary and final seal. The
five-view runner calls `verify_ready.verify()` before creating its output or
starting K1a. This recomputes the whole 12-prompt smoke, native-file closure,
exact oracle, clean drain, build hashes and every real request's census stream.
The failed c-smoke is retained, rejected by the real analyzer and never used
as positive validation. Positive real-stream validation is a mandatory
conditional gate, not a CPU preparation claim. Per-operation native waits use
600 seconds, at least four times the measured parent cold phase; admission
also requires that ratio against the new smoke. Presence, format and exactness
are the in-run data checks, without elapsed-time proof limits.
