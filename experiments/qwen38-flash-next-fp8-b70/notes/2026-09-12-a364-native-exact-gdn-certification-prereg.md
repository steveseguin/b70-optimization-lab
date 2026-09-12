# Preregistration: A364 - certification of the C++ exact serial GDN mode on the MTP1 line

## Result that motivates this

A361/A362 (stage v2 `runtime-gdn-roundstate-bbae3c5-b70`, promoted MTP1 diag line, exact-2K rows):

| arm | GDN verifier rows | M=2 verify step (ms) | warm exact-2K rows (tok/s) | rows |
|---|---|---|---|---|
| A361 | vLLM Python serial path (promoted) | 42.62 | 37.46 / 37.48 | afffd211 x3 |
| A362 | extension exact serial mode, barrier on | **33.69** | **45.73 / 45.89** | afffd211 x3 |

The kernel-level probe is bit-identical for the mode; the server holds the promoted hash on
every row; the two-row verify step loses the 8.7 ms serial-path tax that A356-A358 could not
attribute to kernels or glue. (A363, the same without the completion barrier, is read before A364
launches; the barrier stays unless A363 is exact and materially faster.)

## Treatment

A364 = the certified A305 frozen-client packet (overlay `6d872457`, tuned map, verifier, client
battery unchanged) with only: the kernel stage swapped to stage v2 (manifest
`runtime-stage-gdn-roundstate-v2-loadable.sha256`, stage build head `bbae3c5…`), the derived
server exports `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0`, `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`,
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1` (+ `VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1`), and
the client's live-server selector checks and identity receipts for those. Generator:
`tools/rewrite-q38-a305-to-a364-native-exact-gdn-certification.py`. Port 19977.

## Gates (the certified client's own)

bench-short x3, the quality screen, exact-2K and exact-4K repeats against the lineage's pinned
hashes (`afffd211…`, `c6193cc6…`), the recovery canary, the official W13-N32 selection receipt,
and the identity receipts. Prediction: every gate passes; short rows and exact-2K rows about 20%
above A305's; exact-4K rate above the certified line by a similar margin.

## Stop rules

Any hash mismatch or client FAIL. A pass makes A364 the new MTP1 line candidate; the two-run rule
(a fresh-server repeat, A365) and the promotion attestation follow before any record claim.
