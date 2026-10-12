# October 12 G4 host-binding repair review

This is the implementation author's repair review, not a new independent agent
review. The earlier independent review, original build/source pins and failed
window remain in `evidence/20261012-g4-row-stride-check/`. Nothing outside packet
39 was edited and no device executable, device discovery or privileged operation
was run during this repair.

## Cause and exact layouts

`integrated::arithmetic::row_bytes(type, K, 6)` correctly uses the runtime's
expanded representation. That format retains signed byte codes, FP32 group
scales, and original block metadata. The validator and old miniature CPU
fixtures omitted the metadata. The validator now calls the authoritative
`iq3::expanded::row_bytes`; the G4 fixture's row-size choice is unchanged.

| Dense shape | Codes + FP32 scales (old rejected expectation) | Retained metadata | Correct expanded stride | Packed stride | Split |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q8 HC K10240 | 11520 | 640 | 12160 | 10880 | 4 |
| Q6 shared/GDN K2560 | 3200 | 180 | 3380 | 2100 | 4 / 1 |
| Q8 shared/GDN K2560 | 2880 | 160 | 3040 | 2720 | 1 |
| Q8 shared down K640 | 720 | 40 | 760 | 680 | 1 |
| Q6 attention K6144 | 7680 | 432 | 8112 | 5040 | 4 |

Split-four changes the reduction tree only. Inputs, intermediate projection
outputs and epilogue outputs remain BF16 (`uint16_t`); weight codes remain
bytes and group scales FP32. Routed IQ2/IQ3/IQ4 rows remain packed.

## Coverage and containment

`g4_fixture.hpp` now owns all twelve cases and the exact binding path used by
G4. `g4_binding_gate.cpp` instantiates it with a host backend and invokes the
real `fused.hpp` validation for all 68 bank bindings. Full-sized address ranges
are reserved on CPU without populating multi-GB weight payloads. Small operands
use the actual builder. This tests bindings, not numerical GEMVs. Both GCC and
icpx pass all twelve cases and fourteen wrong-stride rejections each. The old
codes/scales-only and packed dense strides must both be rejected. Native build
and seal require current source-bound receipts from this gate.

The shared `case_runner.hpp` catches only `invalid_argument` validation and the
explicit `ByteMismatch` class as case failures. CPU injection rejects case six,
fails bytes in case seven, then verifies all twelve attempts and cleanups.
Infrastructure injection at case three verifies stop, with failure reporting
before cleanup. Allocation, device exceptions, profiling and requested stops
remain infrastructure errors. Known failures get their own class JSON and
summary row with null timings; they never enter dispatch. The wrapper permits
partial and all-case failure completion and reports case status separately from
infrastructure success. Fourteen wrapper mock groups passed.

The modified arithmetic CPU fixtures retain the metadata trailer and initialize
only actual FP32 scale slots. Four fresh compiler/process runs passed 10,400
finite/control comparisons and 7,200 rejection checks. The same 36 GCC
nonfinite byte mismatches remain recorded as unqualified failures; icpx has
none. No tolerance or quality gate was relaxed.

## Assembly and combined experts

Everything from `position_valid` onward in `fused.hpp` is byte-identical to the
prior source. `fused_sycl.hpp` and original runtime tails are unchanged.
`repair-image-identity.json` verifies both previous embedded SPIR-V modules
remain byte-identical in the rebuilt native executable. Therefore the retained
32-kernel offline assembly and independent loop review still apply; recompiling
identical device images with ocloc is unnecessary. K0 is an identical copy of
G4 with compile-smoke selected at runtime.

The existing `expert-act-iq2` and `expert-act-iq3` cases already fuse BOTH status
checks and activation into paired gate/up. Both stay rejected for added
predicate spills. No duplicate combined case was added or admitted. IQ2
checks-only remains admitted; IQ3 checks-only remains rejected for one extra
loop instruction. The wrapper retains these assembly exclusions even when
screening timings are faster. Alternative expert savings are never summed.

## Timing and retained evidence

The original five rows and 200 samples per arm are preserved. Their table
states microseconds per entire launch group, eight rotated full-size banks,
weight bytes per buffer, groups/token and the difference-of-medians saving
per token. Rotation evidence comes from the archived native source path, not
a cache counter. Every completed weight payload exceeds 8 MiB. The remaining
seven cases have no old measurement.

New summary rows state milliseconds per group, rotation policy and
`(unfused_ms-fused_ms)*groups_per_token`. These are one-window chain screenings;
no whole-model or repeat-window speed verdict is claimed. Original full-model
host evidence is retained, not rerun: this repair changes host validation and
harness behavior, while scalar epilogue arithmetic and device images are
unchanged. Fresh coordinator K0/G4, full-model native parity and repeats remain
pending under the new output names in `WINDOW.md`.
