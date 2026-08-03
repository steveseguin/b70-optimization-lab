# Laguna INT4 affine tile-record first static result

Date: 2026-08-03 America/Toronto

Status: **candidate `a0c7ae628ff1` closed at the preregistered static gate**.
The compile-only AOT action ran once. The emitted executable was not run, and
no XPU runtime, model, service, reset, or privileged action occurred.

## Result

The affine implementation removed the old dynamic candidate's 98-instruction
addressing regression, but the fresh two-kernel comparison was not a valid
pass:

| kernel | instructions | ALU | sync metric | DPAS | unpredicated mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| archived ordinary control | 370 | 320 | 9 | 2 | 33 | 128 |
| fresh selector-false control | 398 | 346 | 10 | 2 | 33 | 128 |
| fresh affine selector-true | 369 | 317 | 10 | 2 | 33 | 128 |

The fresh selector-false control failed to reproduce the archived 370/320/9
identity. Source inspection explains the contamination: affine tensors and
copy/prefetch objects are declared unconditionally, while only their uses are
guarded by `if constexpr (affine_tile_records)`. IGC retained enough setup in
the selector-false instantiation to add 28 instructions. Therefore the
apparent fresh `369 < 398` comparison is invalid and must not be reported as a
29-instruction win.

The candidate also independently missed the frozen synchronization/topology
anchor: its sync metric is 10 rather than 9, and its assembly contains four
`sync.allrd` operations while the archived ordinary control contains none.
The ordinary load/store/send opcode counts, 2 DPAS, 33 unpredicated multiplies,
GRF128, and absence of executable scratch/spill were preserved. Total
instructions did clear the numerical ceiling, but the gate requires every
condition, so `a0c7ae628ff1` is a static failure and is not authorized for
timing.

The earlier dynamic implementation remains a useful negative rather than a
comparison control: it was 468 instructions, 418 ALU, and sync metric 14. The
new 369-instruction selector-true result is evidence that affine construction
removed its dominant source overhead; it is not correctness, performance, or
memory-feasibility evidence.

## Preserved identities

- preregistration main-repo commit:
  `e200b179405fa806b79431980d110d1120f40d32`;
- candidate source commit:
  `a0c7ae628ff1249c3fb105220b4dd664b960ad95`;
- candidate base / actual old failed source commit:
  `7af3f622d9bf0850661d69045fab18a188ca83f4`;
- compile-only artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-tile-record-a0c7ae628ff1-20260803T010500`;
- analyzer report SHA-256:
  `9ffe635ab8f7c378530039b9251cc55c3d0485f83a84c2eb38a807b159a53da3`;
- fresh selector-false assembly SHA-256:
  `7333d8bf6483c3da2ee90ae5a671672f47fd87ea64f24016bcedfadfd854a9c2`;
- fresh selector-true assembly SHA-256:
  `d7a31fdd8867fcadd85be12a403099de4f8b97c62294e57fe4a5f8a381c460a5`.

The output executable exists only as compiler output at
`igc_int4_mainloop_probe`; it was never invoked.

## Next source-only successor

Do not rerun `a0c7ae628ff1`. A distinct source successor may package all affine
objects into a state returned by a compile-time lambda: the true branch builds
the rank-3/rank-2 views and copy payloads, while the false branch returns an
empty state. Accesses remain inside true `if constexpr` branches. This directly
targets the selector-false contamination without changing the record format or
arithmetic.

That successor needs a new immutable source commit and a new preregistration
before another compile. Its fresh selector-false assembly must recover the
archived 370/320/9 identity, and selector-true must also recover sync metric 9
and eliminate the extra `sync.allrd` topology before it can pass. No threshold
may be relaxed based on this result.

The 13.5-GiB/rank net persistent-growth hard stop and device quarantine remain
unchanged. The protected 125.461973 conventional tok/s record remains the
current record.
