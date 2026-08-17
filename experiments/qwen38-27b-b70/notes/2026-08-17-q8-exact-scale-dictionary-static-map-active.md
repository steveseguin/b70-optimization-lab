# Qwen3.8 Q8 exact-scale dictionary: static-map retry

Date: 2026-08-17  
Status: **closed; safe but `5.360%` slower**
Owner: ASRock 2x B70 reference host

## Hypothesis

The first exact 11-bit scale-plane prototype established that all 840,417,280
Q8 blocks in the pinned Qwen3.8-27B artifact are representable without loss.
Its slow binary-search encoder completed a real TP2 one-token decode, but model
setup took minutes. Two runtime lookup-table revisions then failed the safety
gate: one segfaulted and one reached the first prompt graph before Level Zero
reported an invalid memory object.

This retry removes that failure mechanism rather than repeating it. The half
scale is split into exponent and ten-bit mantissa fields. The model uses:

- 510 exponent-zero patterns; and
- the same 128 mantissas for each normal exponent 1 through 8.

Two compile-time 1,024-entry `uint16_t` maps can therefore encode either field
directly inside the reorder kernel. They require no runtime USM allocation, no
cross-context pointer, and no deferred lifetime. The packed representation and
decode arithmetic remain bit-exact to the already audited codec.

## Bound and gates

The ideal traffic saving remains only 1.838235% of ordinary Q8_0 weights, so a
perfectly scaling result would be about 37.46 tok/s from the accepted 36.773
tok/s baseline. This is an incremental exact optimization, not by itself a
route to 40 tok/s.

Execution order:

1. reconstruct an isolated source from the retained slow revision;
2. replace only the encoder search/allocation with compile-time maps;
3. build with `-j2` under 6 GiB RAM / 8 GiB swap bounds;
4. run `p64/n1` first under 8/10 GiB bounds to exercise prompt and decode;
5. require zero Xe/GuC fault/reset/hang and exact output before any speed test;
6. only then run a same-binary codec-off/on position-balanced bracket.

Do not touch the accepted source or binaries. If prompt processing again
fails, close the format as incompatible with an unmodified secondary matrix
path and do not attempt another device-table revision.

## Implementation and safety result

The final revision put two 1,024-entry `uint16_t` maps in the reorder
translation unit. It made no runtime USM allocation and left the retained
packed decoder unchanged. IntelLLVM 2026.1.1 built the BMG-G31 AOT image under
the 6/8 GiB build bounds.

A bounded `p64/n1` TP2 run completed in 19.18 seconds, including prompt and
decode, with `VERIFY_MISMATCH=0`. It reported a 9,338,944 KiB maximum RSS and
left both B70s normal with no Xe/GuC fault, reset, timeout or hang. This closes
the invalid-memory-object failure mechanism from the prior runtime lookup
revisions.

Candidate binary identities:

- `llama-bench`: `c6e7282119bea665b3f5b7a27e369c148a2ef9e38ea28af0dbcba5d42a9b9a22`;
- `llama-cli`: `2a3c2c8cd518f0204014a799780efc4e0e8d3399394979a3dc0544562dcb0107`;
- `llama-server`: `4ed07c3734745d002f1c9a6711e8d1c08c3d91557b894084a8769d6ac07b6770`;
- `libggml-sycl.so.0.19.0`:
  `37dfb129b08a1b2c04b40b975122c59817b6eb0ece2157b99dbac59c08ba6807`.

## Performance result

The screen used fresh processes in order `control, candidate, candidate,
control`, `p64/n256/r3`, equal TP2, F16 KV, FlashAttention, batch 1024 /
ubatch 256, and identical accepted runtime doors. The control is the promoted
one-chain binary; the candidate uses the previously audited neutral oneAPI
2026.1.1 refresh plus this codec.

| Position | Arm | Decode tok/s | Within-run stdev |
| ---: | --- | ---: | ---: |
| 1 | control | 36.549878 | 0.041000 |
| 2 | static-map codec | 35.344981 | 0.153014 |
| 3 | static-map codec | 34.712627 | 0.070479 |
| 4 | control | 37.475197 | 0.006705 |

The pooled control is `37.0125375 tok/s`; the pooled candidate is
`35.0288040 tok/s`, a **`-5.359626%`** regression. Both candidate runs were
slower than both controls. All four runs reported the same fusion census and
`VERIFY_MISMATCH=0`, and the post-run GPU gate was clean.

The compile-time maps therefore solve setup safety but not decode efficiency:
the 11-bit extraction and dictionary reconstruction cost more than the ideal
1.838235% scale-plane traffic reduction saves. The candidate failed the
performance gate, so no 12-prompt output oracle, semantic suite, endpoint
headline, repro promotion or LocalMaxxing submission was attempted.

## Retained reproduction

Apply the accepted full Q8 stack, then the retained slow codec patch, then:

[`q8-exact-scale-dict11-static-map-negative-20260817.diff`](../patches/q8-exact-scale-dict11-static-map-negative-20260817.diff)

The static-map increment SHA-256 is
`dd6cf78827ec11cee3c6fe0f046e165efe2d0005efc16c0523581bd1494eb31a`;
`git apply --check` passes against the retained slow revision. Structured
measurements and raw-log hashes are in
[`2026-08-17-q8-exact-scale-dictionary-static-map-negative.json`](../data/2026-08-17-q8-exact-scale-dictionary-static-map-negative.json).

Raw local evidence remains under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-scale-static-map/`.
