# Chunk-corruption D7 v2b: green with complete D1/D2 coverage

Date: 2026-08-23. Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-chunkdiag-d7-20260823-d1d2-v2b`.

## Outcome

All seven two-chunk dose rows completed 512 tokens with zero cached prompt
tokens. The quality battery stayed green and the long-context needle was
exact: `B70_QWEN36_NEEDLE_20260609`. This reproduces the expected D7 side of
the dose boundary under instrumentation.

The D1/D2 validator passed:

- D1: 15,537 records; all seven requests have group 0/1/2 allocate/free
  coverage, twelve prefill metadata records, and zero live-slot collisions.
  The consumed triplets were 20/26/32, 41/47/53, 62/68/74, 83/89/95,
  104/110/116, 125/131/137, and 146/152/158. Every triplet was freed; D1's
  final interpretation remains pending the eighth request.
- D2: 28 records, including the expected fourteen rank-0/layer-0
  `pre_native` call-site records. Every request observed flags false at
  computed tokens 0 and true at 1024.

Evidence SHA-256 values:

- D1: `afd0a18766e6e9d99abaa74478c312d422e2ed8e1c920e1e6bb375a00f4edcc7`;
- D2: `8744a38fc881c314abc7c0f83d970c09da9c817756f2d7d350f1a5f70c6cfb01`;
- validator: `751c50cd94634f0afc088d5a228aa91700c79310b99043bfe58cfbdae8e893b9`;
- benchmark: `a6eed7f3209e25711a72285b35d699abd96f8824313c292801365a12a49e9c67`;
- quality: `2d213ce58aecd5f454a460287051d957daffe0167e2e64f7325758f2b6f6bea1`.

The isolated cache input and output manifests are byte-identical at
`8ce2ed4646f6fa33563c20619d382e5d13b3a7b60e609b03230e968c608b55b3`;
the log has no cache-write marker. The recovered source cache also verifies
unchanged.

## D4 safety hardening

The common runner performs its cache postflight only when its aggregate
return code is zero. D4 is expected to return nonzero when the needle turns
red, so the diagnostic driver now independently verifies the sealed cache and
write-marker absence before interpreting quality, regardless of runner code.
This closes the last path by which an expected correctness failure could skip
cache protection.
