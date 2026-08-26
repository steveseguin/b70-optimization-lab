# Qwen3.6 embedded-MTP Q8/q8KV TP1 SYCL-graph quality R1 result

State: **quality-battery-certified; covers all seven q8KV graph curve cells**.

The fresh isolated target-only service passed all 13 preregistered requests:
four exact canaries, eight identical-output repeats with one normalized hash,
and the long-context needle. The needle requested 31,744 context tokens and
produced approximately 29.4K actual prompt tokens: 29,403 by the suite's raw
prompt count and 29,415 by API usage accounting inside the 32,768-token
service. Every response reported `cached_tokens=0`.

The server emitted positive graph evidence: 169 requested, eight
recorded/created, 84 direct cache replays, and 92 total replays on SYCL device
0 with cache limit 8. Compatibility rejection, unsupported device, update, and
recreate counters were zero. `cache_full=77` keeps the service classification
mixed/partial rather than fully graph certified end-to-end.

This one battery covers 0/2K/4K/8K/16K/24K/32K because all seven curve cells
share the exact embedded-MTP Q8_0 artifact, fa0 source and three-patch chain,
graph-enabled build, cache-8 environment, and TP1/MTP0/q8_0-KV selectors. The
checksum-bound curve artifacts separately supply graph evidence at every
depth. Depth-0 prefill and all decode phases retain their curve classifications;
2K through 32K prefill remains mixed partial.

This quality pass does not turn graph mode into a speed optimization. Against
the matching graph-off q8KV curve, graph-on was slower at all seven depths in
both phases, averaging **-1.35% prefill** and **-1.52% decode**. Graph-on is
therefore preserved as quality-certified coverage and mechanism evidence while
the faster graph-off measurements remain protected.

Cleanup passed, and a post-result check found no target server or port-19438
listener. The structured result binds every raw file, exact output hashes,
repeat hash, needle, cache-zero accounting, model/source/build identity, graph
backend, and the 33-entry server DSO closure.

The immutable terminal receipt deliberately uses the inherited exact-depth
schema, leaves `quality_claim_authorized=false`, and requires tracked
adjudication. This tracked result records that the independently verified
battery satisfies the seven-cell quality prerequisite; it does not itself
authorize site ingestion, record submission, or replacement of protected
graph-off speeds.
