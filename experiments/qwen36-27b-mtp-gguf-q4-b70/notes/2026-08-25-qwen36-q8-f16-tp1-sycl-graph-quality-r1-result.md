# Qwen3.6 target-Q8/F16 TP1 SYCL-graph quality r1 result

State: **quality-battery-certified; covers all seven R4 F16 curve cells**.

The fresh, isolated cache-8 graph service passed all 13 preregistered requests:
four exact Qwen3.6 canaries, eight identical-output repeats with one normalized
hash, and the long-context needle. The needle was requested at 31,744 context
tokens but produced approximately 29.4K actual prompt tokens: 29,403 by the
suite's raw-prompt count and 29,415 by API usage accounting
inside the sealed 32,768-token service. Every response reported
`cached_tokens=0`.

The server emitted positive graph capture and replay evidence: 169 requested,
8 recorded/created, 84 direct cache replays, and 92 total replays on SYCL device
0 with cache limit 8. Compatibility rejection, device unsupported, update, and
recreate counters were all zero. `cache_full=77` preserves the existing claim
boundary: the service workload includes mixed/partial graph prefill; it does not
upgrade those phases to fully graph-certified.

This single battery legally covers contexts 0/2K/4K/8K/16K/24K/32K because all
seven R4 cells share the exact Q8_0/F16 TP1 MTP0 source, model, build, graph
environment, and selectors, while the R4 curve supplies graph evidence at each
depth. Depth-0 prefill and every decode phase retain their R4 graph
classification; 2K through 32K prefill remains disclosed as mixed partial.

Cleanup passed, no target server or port-19436 listener remained, and the raw
root is preserved at
`/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-quality-20260825-r1`.
The machine-readable result seals every raw hash, the server's 33-entry DSO
closure, runtime/model/source identities, and the ordered three-patch chain.

No raw speed was changed or reinterpreted as HTTP speed. This result does not
authorize a record submission and does not replace any protected graph-off
value.

The immutable terminal receipt exposes an inherited-writer plumbing
contradiction: it uses the exact-depth terminal schema and retains
`quality_claim_authorized=false` even though its state says the battery passed.
The raw receipt remains untouched and checksum-bound. This tracked adjudication
classifies the independently verified battery as satisfying the R4 quality
prerequisite, not as publication authority; a separate ingestion packet must
bind the qualified cells into the site.
