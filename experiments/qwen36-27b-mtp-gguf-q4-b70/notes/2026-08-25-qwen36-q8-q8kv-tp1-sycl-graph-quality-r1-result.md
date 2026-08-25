# Qwen3.6 target-Q8/q8_0-KV TP1 SYCL-graph quality r1 result

State: **quality-battery-certified; satisfies the prerequisite for all seven
q8-KV R2 curve cells**.

The fresh isolated q8_0-KV service passed 4/4 exact Qwen3.6 canaries, 8/8
identical-output repeats with one normalized hash, and the long-context needle.
The needle was requested at 31,744 tokens but measured approximately 29.4K
actual prompt tokens: 29,403 by the suite's raw-prompt count and 29,415 by API
usage accounting inside the 32,768-token service. All 13 responses reported
`cached_tokens=0`.

The server confirmed the q8_0 KV selector (`K (q8_0)` and `V (q8_0)`, 544 MiB
each) and emitted positive graph evidence: 169 requested, 8 recorded/created,
84 direct cache replays, and 92 total replays on device 0 with cache limit 8.
Compatibility rejection, device unsupported, update, and recreate were zero.
`cache_full=77` keeps prefill classified as mixed/partial; it is not upgraded to
fully graph-certified.

One battery covers 0/2K/4K/8K/16K/24K/32K because all R2 cells share this exact
q8_0-KV model/source/build/environment tuple and the R2 curve separately holds
mechanism evidence for every depth. Depth-0 prefill and every decode phase keep
their R2 classification; 2K through 32K prefill remains mixed partial.

Cleanup passed, no target server or port-19437 listener remained, and all raw
artifacts are checksum-bound under
`/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-sycl-graph-quality-20260825-r1`.
The structured result also seals the 33-entry server DSO closure, three-patch
chain, q8 selectors, model, source, and runtime identities.

The packet tests passed 5/5 before launch. Re-running them after completion
passes four and has one expected failure solely because that prelaunch-only
test asserts that the run root does not exist; this is not a run failure and
is not represented as a post-run 5/5 claim.

The immutable raw terminal intentionally carries the inherited exact-depth
schema and `quality_claim_authorized=false`; this is a known writer/authority
plumbing contradiction, not a failed battery. This tracked adjudication marks
the quality prerequisite satisfied but does not itself authorize publication.
A separate ingestion packet is required. No raw speed, protected graph-off
value, or record-submission authority changed.
