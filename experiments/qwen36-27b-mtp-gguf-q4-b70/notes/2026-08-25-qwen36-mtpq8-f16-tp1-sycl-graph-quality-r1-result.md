# Qwen3.6 embedded-MTP Q8/F16 TP1 SYCL-graph quality R1 result

State: **quality-battery-certified; covers all seven embedded-MTP graph curve cells**.

The fresh isolated target-only service passed all 13 preregistered requests:
four exact canaries, eight identical-output repeats with one normalized hash,
and the long-context needle. The needle requested 31,744 context tokens and
produced approximately 29.4K actual prompt tokens: 29,403 by the suite's raw
prompt count and 29,415 by API usage accounting inside the sealed 32,768-token
service. All 13 responses reported `cached_tokens=0`.

The server emitted positive graph evidence: 169 requested, eight
recorded/created, 84 direct cache replays, and 92 total replays on SYCL device
0 with cache limit 8. Compatibility rejection, unsupported device, update, and
recreate counters were zero. `cache_full=77` keeps the claim narrow: this
service workload contains mixed/partial graph work and is not fully graph
certified end-to-end.

One battery covers contexts 0/2K/4K/8K/16K/24K/32K because all seven curve
cells share the exact embedded-MTP Q8_0 artifact, fa0 source plus three-patch
chain, graph-enabled build, cache-8 environment, and TP1/MTP0/F16 selectors.
The curve separately supplies phase-aware mechanism evidence at every depth.
Depth-0 prefill and every decode phase retain their curve classifications;
2K through 32K prefill remains mixed partial.

The quality pass does not change the performance conclusion. Graph-on remained
slower than matching graph-off at every curve depth, so graph-on is preserved
as quality-certified coverage and mechanism evidence while the faster
graph-off measurements remain protected.

Cleanup passed, and a post-result check found no target server or port-19436
listener. The structured result binds every raw file, exact output hashes,
repeat hash, needle and cache-zero accounting, model/source/build identity,
graph backend, and the 33-entry server DSO closure.

The immutable terminal receipt uses the inherited exact-depth schema and keeps
`quality_claim_authorized=false`. The tracked adjudication records that the
independently verified battery satisfies the seven-cell curve's quality
prerequisite; it does not itself authorize site ingestion, record submission,
or replacement of any protected graph-off speed.
