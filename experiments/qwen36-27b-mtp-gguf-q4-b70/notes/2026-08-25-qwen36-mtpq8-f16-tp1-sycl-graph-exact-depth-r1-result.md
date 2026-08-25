# Qwen3.6 embedded-MTP Q8/F16 TP1 SYCL-graph exact-depth R1 result

State: **passed seven raw graph cells; negative optimization result; quality pending**.

| Active context | Prefill tok/s | Decode tok/s | Prefill graph phase | Decode graph phase |
|---:|---:|---:|---|---|
| 0 | 900.476067 | 19.363945 | capture-and-replay, no cache full | verified capture-and-replay |
| 2K | 880.567469 | 19.181638 | mixed partial, cache-8 full | verified capture-and-replay |
| 4K | 857.097412 | 19.077044 | mixed partial, cache-8 full | verified capture-and-replay |
| 8K | 819.594441 | 18.846108 | mixed partial, cache-8 full | verified capture-and-replay |
| 16K | 755.794333 | 18.413817 | mixed partial, cache-8 full | verified capture-and-replay |
| 24K | 700.160452 | 18.006725 | mixed partial, cache-8 full | verified capture-and-replay |
| 32K | 650.649241 | 17.616797 | mixed partial, cache-8 full | verified capture-and-replay |

All seven exact-depth rows passed. Every decode phase replayed all 641
requested graphs with no cache-full, compatibility-rejection, unsupported
device, update, or recreation event. Depth 0 also fully captured and replayed
prefill. At 2K through 32K, the preregistered fixed cache records and replays
eight prefill shapes and reports the remaining shapes as `cache_full`; those
prefill phases are mixed partial graph, not fully graph certified.

This is useful coverage and mechanism evidence, but not a speed optimization.
Against the matching graph-off embedded-MTP Q8/F16 curve, graph-on was slower
at every depth in both phases. The unweighted mean deltas were **-1.25% prefill**
and **-2.19% decode**. The graph-off values therefore remain the preferred
performance measurements and must not be replaced.

The structured result checksum-binds every raw file and preserves the complete
model, source, graph-enabled build, three-patch chain, binary, graph backend,
and 32-library closure identities. Cleanup passed with no terminal error.
Quality is still pending, so this packet does not authorize site publication,
quality claims, record submission, or any change to protected or featured
speeds.
