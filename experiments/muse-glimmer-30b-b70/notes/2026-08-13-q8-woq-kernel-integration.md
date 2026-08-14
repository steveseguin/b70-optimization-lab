# Q8_0 oneDNN WOQ kernel integration

Date: 2026-08-13

Closeout: the later ARGMAX/local-winner reuse and final serving stack crossed
the full-256 century gate twice. This file remains the earlier fixed-N16
integration checkpoint. Use the [promoted result](../../../results/muse-glimmer-30b-q8-woq-b70/README.md)
and [repro](../../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
for the final identity; do not resume from the “Next kernel step” below.

## Scope

This is a no-training target-kernel experiment. It is a separately declared
Q8-prefill / BF16-activation, S8-group32 WOQ decode target, not a BF16 or
lossless result. The BF16 DFlash assistant is unchanged.

The source experiment is default-off under
`GGML_SYCL_Q8_0_WOQ_BF16=1`. It uses direct-strided oneDNN JIT WOQ for the six
large Muse projection classes. `GGML_SYCL_Q8_0_WOQ_FIXED16=1` pads target
widths 1..16 to one N16 primitive and uses an N16 temporary destination before
copying the valid prefix.

## Kernel evidence

The first real target p16 screen reduced the target verifier pass from about
146.14 ms to 35.10 ms (roughly 4.16x). The initial 64-token integrated screen
exceeded 150 tok/s arithmetic mean, but a fresh-process JSON output alternated
between two hashes. The cause was narrowed to arithmetic/layout sensitivity
plus an unsafe graph conversion cache; fixed N16 with strictly local,
LIFO-safe conversions produced four identical no-spec fresh starts and two
identical speculative fresh starts.

Stable speculative 64-token pair:

- A: 77.554 / 132.005 / 248.335 tok/s, mean 152.631;
- B: 78.372 / 130.987 / 255.598 tok/s, mean 154.986;
- hashes: `f45a2f2c58f1ca34 / 2ca4135046a15a71 / 32dc3aebb11684a4`;
- proposal totals: `155 / 126 / 65`;
- accepted: `48 / 53 / 58`.

Evidence:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/q8-woq-fixed16-spec-smoke64-20260813.jsonl`
(note that later exploratory arms reused this path; preserve run logs with the
config identity when summarizing).

## Full 256 result

The best valid fixed-N16, graph-conversion-cache-off full run measured:

- prose 69.914 tok/s;
- code 104.515 tok/s;
- JSON 120.134 tok/s;
- arithmetic mean **98.188 tok/s**;
- target rounds `82 / 56 / 49` from accepted `174 / 200 / 207`;
- round costs `44.654 / 43.739 / 43.489 ms`.

The exact remaining uniform saving for arithmetic mean 100 is about
**0.795 ms per target round**. This is not yet a sustained >100 result.

Evidence was captured before a later exploratory overwrite at:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/q8-woq-fixed16-spec-full256-20260813.jsonl`;
the recorded SHA at capture was
`dae6a200141141771e599643030bf0e6803193962e3d5eb233eda4378e1c849f`.

## Rejected variants

- Width-specific N1..N16 WOQ is faster but fresh-process JSON output can flip;
  reject for deterministic promotion.
- Direct persistent conversion caching keyed only by arena address was unsafe.
  Adding tensor identity fixed that correctness issue, but lazy direct-USM
  allocations were slow and selected the alternate JSON path; reject.
- Writing actual N16 directly to the arena destination (rather than the common
  temporary destination) also reintroduced the JSON flip; reject.
- Re-enabling the ordinary BF16 graph conversion cache did not improve the
  full result and changed long-JSON acceptance; reject for the current target
  configuration.

## Next kernel step

Implement a graph-local fixed-N16 conversion cache with explicit allocation
stack ownership and reverse-order teardown. Keep WOQ oneDNN scratch outside
the strict VMM stack. This should reuse exact shared Q/gate and FFN gate/up
activations without stale arena aliases, unordered-map destruction, or direct
allocation latency. It needs at least ~0.8 ms/round net improvement, exact
fresh-process hashes, and a repeated full 256 confirmation before promotion.

Production BF16 services were restored and healthy after every GPU window. No
reboot was needed and no source commit was made.
