# Laguna INT4 affine one-cursor static result

Date: 2026-08-03 America/Toronto

Status: **automated/count/topology and semantic address gates passed at
370/318; frozen literal manual address-form gate missed**.

The preregistered compile-only action ran once. Its executable was not invoked,
and no XPU runtime, device component, model, service, reset, recovery, or
privileged action occurred.

## Objective result

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector-false control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| clean scale-clone `86c1c8b` | 371 | 319 | 9 | 0 | 2 | 33 | 128 |
| bounded two-cursor `dd59739` | 377 | 325 | 9 | 0 | 2 | 33 | 128 |
| one-cursor `6832654` | 370 | 318 | 9 | 0 | 2 | 33 | 128 |

The unchanged analyzer passed every automated gate at the stricter 371 ceiling:
selector-false identity, candidate instruction ceiling, arithmetic anchors,
exact fresh control/candidate memory/send/sync opcode histogram, sync identity,
GRF128, and no executable spill/scratch. Fresh selector-false is body-identical
to the archived control apart from options/hash header and terminal hash
sentinels.

The supplemental opcode gate also passed exactly:

```text
mov  144  (ceiling 145; scale-clone base 143)
add   59  (ceiling  59; scale-clone base  59)
mul   35  (ceiling  35; scale-clone base  37)
macl   1
mad    1
shl   11
add3   0
```

No executable dynamic `mul ... 1152`/`0x480` remains. The six prologue weight
bases lower directly into the payload at offsets 0, 1152, 2304, 3456, 4608,
and 5760; the five temporary address-to-payload moves from `dd59739` are gone.
The combined future-weight block shrank from ten to nine instructions, the
scale-clone issue remains four, memory sends/descriptors are unchanged, and no
second record cursor/phi exists.

## Frozen literal manual-gate miss

The generated future addresses are semantically correct but do not have the
literal form preregistered for acceptance.

Source expresses the future address after copy `k` as:

```text
advanced_cursor(k + 1) + 5760 = record(k + 6)
```

IGC reassociated the induction and sank the cursor increment to the loop latch:

```text
current_cursor(k) + 6912 = record(k + 6)
cursor += 1152 at the latch
```

Thus the frozen K256/d6 address sequence is exact: copy issues records 0..7,
future prefetch issues records six and seven, and no record eight is issued.
Before-unification IR and final assembly show one cursor, base retarget followed
by rank-2 X/Y updates and the unchanged send, no intervening second base write,
and one latch increment. This is a legal algebraic normalization and not an
out-of-bounds or wrong-record result.

However, the preregistered manual gate was assembly-facing and explicitly
required adding 5760 to an already-advanced cursor at the future send. Only the
prologue clause explicitly allowed normalization. Retroactively accepting
current+6912 would weaken the frozen wording after seeing the result.
Therefore:

- automated/count/topology/sync gates: pass;
- semantic record-address audit: pass;
- frozen literal manual address-form gate: miss; and
- preregistered full no-regression/static-address-lowering pass: **not awarded**.

This source is preserved as a literal gate-shape failure despite producing the
best candidate static count in the affine-record sequence. No timing or
integration is authorized.

## Preserved identities

- preregistration main-repo commit:
  `b8341497a9bb6f4bb67884af07c1d3c3bc41b418`;
- candidate head:
  `683265470c5cdb30115c1027e6f0ad6780819d7e`;
- source commit:
  `2dc2b2a867ffd7d07428e1d65e584c4d3b64afa3`;
- candidate base:
  `dd597391f22f6a5f15ccbc0c6b115005970b4575`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-one-cursor-683265470c5c-20260803T020000`;
- analyzer report SHA-256:
  `4f83cbb2fd3d7ad77ccd76228557d2fb823b33cf1c8145074935f2e5fc56dabc`;
- selector-false assembly SHA-256:
  `c61792d1e495b998c84074695af2b11f095c150a5e297ad5d498f8e8b0661f91`;
- selector-true assembly SHA-256:
  `946f64d14566ae84a12b7eb94b5b4342700ee4faae1f5284168ab3cf81fd9d69`.

## Prospective canonical-form successor

Normalized equivalence may be accepted only under a new prospective gate and
new source commit. The smallest honest successor is to express the form IGC
selected directly:

1. keep the copy cursor at record `k` through the future-prefetch block;
2. derive the future base as `copy_cursor + prefetch_dist * 1152`, which is
   record `k+6` for the frozen distance;
3. advance the cursor once after the future-prefetch conditional, before the
   next main-loop iteration; and
4. prospectively require the final one-cursor `current + 6912`, future send,
   and single +1152 latch induction form.

This changes source ordering and aligns source, frozen gate, IR, and expected
ISA without rerunning or reinterpreting `6832654`. It requires a new immutable
source, tests, preregistration, and one new compile-only AOT action.

No device or timing action is authorized. The inherited prologue distance
caveat, 15.1875-GiB/rank allocation, 13.5-GiB/rank net-growth hard stop,
corrected PCIe/NVMe quarantine, and protected 125.461973 conventional tok/s
record remain unchanged.
