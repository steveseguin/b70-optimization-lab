# Laguna INT4 affine weight-cursor static result

Date: 2026-08-03 America/Toronto

Status: **bounded cursor mechanism passed the 378-instruction static ceiling;
not promoted because it regressed the clean scale-clone base by six
instructions**.

The preregistered compile-only action ran once. Its executable was not invoked,
and no XPU runtime, device component, model, service, reset, recovery, or
privileged action occurred.

## Result

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector-false control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| scale-clone base `86c1c8b` | 371 | 319 | 9 | 0 | 2 | 33 | 128 |
| weight-cursor `dd59739` | 377 | 325 | 9 | 0 | 2 | 33 | 128 |

The unchanged analyzer passed every automated hard gate at the frozen 378
ceiling: selector-false identity, candidate arithmetic anchors, exact fresh
control/candidate memory/send/sync opcode histogram, sync identity, GRF128, and
no executable spill/scratch. Fresh selector-false is body-identical to the
archived control; only the options/hash header and two terminal hash sentinels
differ.

Manual inspection also passed the bounded address-lowering gate:

- the two recurring predicated dynamic `mul ... 1152` operations in the prior
  weight copy and future-weight-prefetch paths are absent;
- the remaining 1152-byte operations are constant prologue address adds and
  two induced cursor increments, not register-by-record-stride multiplies;
- before-unification IR shows `setBlock2DAddressPayloadBase`, then rank-2 X/Y
  updates, then the unchanged weight send at every issue, with no second base
  write between retarget and send;
- the prefetch cursor phi starts at record zero, advances through prologue
  records 0..5, and enters the main loop at record six; the copy cursor phi
  starts at record zero; guarded future prefetch advances only after records six
  and seven are issued; and
- the four-instruction cloned-scale issue block, weight sends, descriptor
  geometry, DPAS/arithmetic sequence, nine `sync.nop`, one `sync.bar`, and zero
  `sync.allrd` are preserved.

The successor therefore validates explicit rank-2 payload retargeting and
pointer induction as a clean synchronization/topology mechanism. It is not yet
the best static source. Relative to the 371-instruction scale-clone assembly,
its opcode delta is:

```text
+7 mov
+1 add
-2 mul
net +6 instructions
```

Five added moves come from the unrolled prologue: source-level cursor mutation
makes IGC form each constant record address in a temporary and then move it into
the payload, whereas the rank-3 base folded each constant add directly into the
payload. A sixth one-time add materializes the record-six prefetch cursor before
the main loop. The remaining two added moves replace the two dynamic base
additions in the copy/future paths; their two removed multiplies keep those
paths equal in raw count rather than lowering the whole kernel.

Per the frozen interpretation, 377 is a bounded mechanism pass but an explicit
instruction/ALU regression from 371/319. This source remains offline and is not
promoted for integration or timing.

## Preserved identities

- preregistration main-repo commit:
  `293ee37b0`;
- candidate source commit:
  `dd597391f22f6a5f15ccbc0c6b115005970b4575`;
- candidate base:
  `86c1c8bdf75bbd84803f4d256b925b3f509e5ea4`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-weight-cursor-dd597391f22f-20260803T014500`;
- analyzer report SHA-256:
  `b091508ff604dba519483a962102257f9beebe7852972e13787f34ee7a39d9a7`;
- selector-false assembly SHA-256:
  `5e1906c94f8cdf9d3c440156d0f2b9742550686e839535f8b547598805858de5`;
- selector-true assembly SHA-256:
  `e1047366a94d02ebc03f7d5ca6143a6179cf7225119c8b55559d54e55bfa9787`.

## Smallest source-only successor

The result points to a narrower one-cursor formulation rather than another
payload mechanism:

1. retain the rank-2 weight payloads and scale clone;
2. keep one mutable copy cursor and one immutable record-zero base;
3. retarget the six unrolled prologue prefetches directly from
   `record_base + k_tile_prefetch * 1152`, allowing their compile-time constant
   addresses to fold into the payload instead of advancing a source cursor;
4. advance the copy cursor once after the main weight copy; and
5. derive the guarded future-prefetch base from that already-advanced copy
   cursor plus `(prefetch_dist - 1) * 1152`, eliminating the separate prefetch
   cursor, its record-six setup add, its payload move, and its recurring
   increment.

For the frozen distance six, after copying group `k` the copy cursor names
group `k+1`; adding five record strides names the required future group `k+6`.
This is a new source question, not an inferred ISA result. It requires a new
immutable commit and preregistration before AOT.

No device or timing action is authorized. The 15.1875-GiB/rank allocation,
13.5-GiB/rank net-growth hard stop, corrected PCIe/NVMe quarantine, and
protected 125.461973 conventional tok/s record remain unchanged.
