# Laguna INT4 compile-time affine-state static result

Date: 2026-08-03 America/Toronto

Status: **candidate `1ef527526e8c` closed at the preregistered static gate**.
The compile-only action ran once. Its executable was not invoked, and no XPU
runtime, model, service, reset, or privileged action occurred.

## Result

Compile-time state isolation repaired the contaminated selector-false control
exactly, but it did not repair selector-true synchronization:

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| archived ordinary control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| fresh selector-false | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| fresh affine selector-true | 369 | 317 | 10 | 4 | 2 | 33 | 128 |

The fresh selector-false instruction body is identical to the archived control.
The only textual assembly differences are the options/hash header (including
the explicit fresh `-TotalGRFNum 128` option) and the two terminal hash
sentinels. This proves the compile-time empty state removed the first
candidate's false-path 398-instruction contamination.

Selector-true still contains four `sync.allrd` operations and ten `sync.nop`
operations instead of zero and nine. The 369 total, 317 ALU, preserved ordinary
load/store/send counts, 2 DPAS, 33 plain multiplies, GRF128, and absence of
executable scratch/spill cannot waive that synchronization failure. This
immutable source is not authorized for timing or integration.

## Preserved identities

- preregistration main-repo commit:
  `4ebc778f60ab0f498f043356f222ace0318ebc3a`;
- candidate source commit:
  `1ef527526e8ca18e7c04dc9bb8b23020e6f8dec2`;
- candidate base / closed first-affine commit:
  `a0c7ae628ff1249c3fb105220b4dd664b960ad95`;
- compile-only artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-state-1ef527526e8c-20260803T013000`;
- analyzer report SHA-256:
  `44d1faea8ed3acb9942dafa230a3ade54867d9421cbb61005674fbed7ab84a05`;
- selector-false assembly SHA-256:
  `2364faf2b1d712674fb80daa278439705d1c9f7a9686ced636aec6baa2bc90c5`;
- selector-true assembly SHA-256:
  `9a6abcc9ae6a7bc468088d8c356880a89fb0aef03aaf6e92fa3470c0ea0115da`.

## Source attribution and next successor

Independent source/ISA review localized all four `sync.allrd` operations to
reuse of the one hoisted mutable scale-prefetch payload. The affine weight
payload is not the direct source. The smallest distinct successor is therefore
hybrid:

1. retain compile-time isolation, the affine rank-3 weight copy/prefetch state,
   and the affine rank-2 scale tensor used for scalar scale loads;
2. remove the hoisted scale-prefetch copy, partition, and payload objects from
   the tuple; and
3. let the two scale-prefetch sites use the preserved TileMajor per-issue
   payload construction, which gave the archived control separate descriptors
   and zero `sync.allrd`.

That hybrid must be a new source commit and new preregistration. It may still
fail by exceeding 378 instructions or retaining waits, so the current gate must
not be relaxed. Do not rerun `1ef527526e8c`.

The memory hard stop, device quarantine, and protected 125.461973 conventional
tok/s record remain unchanged.
