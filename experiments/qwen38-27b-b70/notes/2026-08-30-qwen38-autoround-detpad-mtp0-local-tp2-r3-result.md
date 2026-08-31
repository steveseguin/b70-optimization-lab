# Qwen3.8 AutoRound INT4 MTP0 local TP2 R3 result

Date: 2026-08-30

Status: **shared TP2 nondeterminism confirmed; speed remains quarantined**

R3 repeated both R2 execution modes from new empty cache/evidence roots on the
two local B70s. All four underlying arms independently passed direct model
verification, the complete 12-prompt/six-class workload, cache-zero checks,
the canary battery, and clean shutdown.

| comparison | complete arrays exact |
| --- | ---: |
| R2 eager vs R3 eager-B | **9/12** |
| R2 compiled-A vs R3 compiled-B | **4/12** |
| R3 eager-B vs R3 compiled-B | **6/12** |

The eager repeat mismatch proves that compilation is not the sole cause. The
compiled mode adds a larger unstable surface, but the correctness repair must
start in the shared TP2 target path.

Eager medians were `17.967661` and `17.973466` tok/s. Compiled medians were
`31.827338` and `32.110001` tok/s. All are diagnostic; none authorizes a speed
claim or MTP.

One tempting explanation was rejected immediately after R3: the quantized GDN
B/A-shaped raw operator was exact in 2,800/2,800 comparisons at every 48--78
token prompt shape plus 128 and 256 rows with the global pad disabled. The
checkpoint also stores `in_proj_a`/`in_proj_b` in FP16, so it already uses the
separate deterministic 256-row B/A path. Do not broaden the INT4 pad on that
negative evidence.

Next: screen identical production-shape INT4 tensors across fresh processes,
then localize the first model-layer divergence if those operators remain
clean. Prefer a causal kernel or ordering repair over whole-device
synchronization; the earlier FP8 campaign already proved explicit collective
`Work.wait()` is sufficient for that lane.

Structured result:
[`../data/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r3-result.json`](../data/2026-08-30-qwen38-autoround-detpad-mtp0-local-tp2-r3-result.json)

Raw B/A operator screen:
[`../data/2026-08-30-qwen38-autoround-int4-gdn-ba-msweep-negative.json`](../data/2026-08-30-qwen38-autoround-int4-gdn-ba-msweep-negative.json)
