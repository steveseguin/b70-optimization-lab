# Qwen3.6 Q4_K_M/F16 TP1 SYCL-graph quality R1 result

State: **quality-battery-certified; covers all seven Q4_K_M/F16 graph curve cells**.

The fresh isolated target-only service passed all 13 preregistered requests: four exact canaries, eight identical-output repeats with one normalized hash, and the long-context needle. The needle requested 31,744 context tokens and produced approximately 29.4K actual prompt tokens—29,403 by the suite and 29,415 by API usage—inside the sealed 32,768-token service. All 13 responses reported `cached_tokens=0`.

The server emitted positive graph evidence: 169 requested, eight recorded/created, 84 direct cache replays, and 92 total replays on SYCL device 0 with cache limit 8. Compatibility rejection, unsupported device, update, and recreate counters were zero. `cache_full=77` keeps the service claim mixed/partial rather than fully graph-certified end-to-end.

One battery covers exact contexts 0/2K/4K/8K/16K/24K/32K because all seven curve cells share the checksum-pinned embedded-MTP Q4_K_M artifact, source plus three-patch chain, graph-enabled build, cache-8 environment, and TP1/MTP0/F16 selectors. Depth-0 prefill and all decode phases retain their curve graph classifications; prefill from 2K through 32K remains mixed partial.

The quality pass does not change the performance conclusion. Graph-on was slower than matched graph-off in both phases at all seven depths: unweighted mean deltas were -8.137743% prefill and -2.333593% decode. Graph-on is retained as quality-certified coverage and mechanism evidence; the faster graph-off values remain protected.

Cleanup passed. The structured result binds every raw file, output hash, repeat hash, needle and cache-zero accounting, complete model/source/build identity, graph backend, and 33-entry server DSO closure. The raw terminal remains authority-closed and requires this tracked adjudication plus separate family ingestion; it does not authorize record submission or protected-value replacement.
