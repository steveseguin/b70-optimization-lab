# Laguna INT4 affine-weight / per-issue-scale-prefetch static result

Date: 2026-08-03 America/Toronto

Status: **candidate `698113420380` closed at the preregistered static gate**.
The compile-only action ran once. The executable was not invoked; no XPU
runtime, model, service, reset, or privileged action occurred.

## Result

The source diagnosis was correct but the resulting address setup remained too
large:

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector-false control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| hybrid selector-true | 386 | 336 | 9 | 0 | 2 | 33 | 128 |

Selector-false again reproduced the archived control. Selector-true removed all
four `sync.allrd`, returned to nine `sync.nop` plus one `sync.bar`, preserved
the complete memory/send/sync opcode histogram, 2 DPAS, 33 plain multiplies,
GRF128, and no executable scratch/spill. The per-issue scale descriptors
therefore repaired the synchronization topology exactly.

However, 386 exceeds the frozen 378-instruction ceiling by eight instructions
and the 370 control by 16. The candidate is a static loss regardless of its
repaired synchronization and must not be timed.

Opcode attribution versus control is consistent with descriptor/address setup:
candidate has 20 more `mov` and eight more `add`, offset by nine fewer `shl`,
two fewer `macl`, and one fewer `add3` (net +16). Three dynamic literal
multiply-by-1152 operations also remain later in the candidate. This exact
hybrid therefore does not satisfy the no-recurring-address-materialization
gate either.

## Preserved identities

- preregistration main-repo commit:
  `072daadfc5e7b389ccc44b3eee6fed2d855bf9b9`;
- candidate source commit:
  `698113420380b3e343a04ab93321c7adf0b1e94e`;
- source base:
  `1ef527526e8ca18e7c04dc9bb8b23020e6f8dec2`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-hybrid-698113420380-20260803T014000`;
- analyzer report SHA-256:
  `a47cea5697bc9f35983079c39682ebc2b8704aeaa284fbeabb9b8dfe23781aff`;
- selector-false assembly SHA-256:
  `8f468564a97274b7b50b3086d589ccd040afe12a42c310a6a03ea972d219504a`;
- selector-true assembly SHA-256:
  `1965518ef854f91c6b6471b4d3dbd9489bc46343762016e8ee7c73594d7dfeb8`.

Do not rerun `698113420380`. A distinct successor would need to retain separate
scale descriptors while hoisting their invariant base/shape fields or otherwise
remove at least eight instructions and all recurring 1152 address
materialization. It requires a new source commit and preregistration.

The memory hard stop, device quarantine, and protected 125.461973 conventional
tok/s record remain unchanged.
