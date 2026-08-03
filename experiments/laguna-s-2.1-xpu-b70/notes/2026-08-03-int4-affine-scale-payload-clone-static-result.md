# Laguna INT4 affine scale-payload clone static result

Date: 2026-08-03 America/Toronto

Status: **scale-payload feasibility sub-screen passed; full tile-record gate
not passed**.

The compile-only action ran once. Its executable was not invoked, and no XPU
runtime, model, service, reset, or privileged action occurred.

## Result

The unused hardware payload-copy intrinsic lowered to one eight-dword region
move per issue and removed the scale descriptor's aliasing and address setup:

| kernel | instructions | ALU | sync metric | `sync.allrd` | DPAS | plain mul | GRF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| selector-false control | 370 | 320 | 9 | 0 | 2 | 33 | 128 |
| scale-clone selector-true | 371 | 319 | 9 | 0 | 2 | 33 | 128 |

Selector-false reproduced the archived control. Selector-true passed every
automated anchor: total at or below 378, exact memory/send/sync opcode
histogram, 2 DPAS, 33 plain multiplies, sync metric 9, zero `sync.allrd`, nine
`sync.nop`, one `sync.bar`, GRF128, and no executable scratch/spill.

Manual inspection also passed the scoped scale gate. The steady future-scale
prefetch block is four instructions: one eight-dword payload clone, two
coordinate-field moves, and the unchanged block-prefetch send. No dynamic
scale-prefetch multiply-by-1152 or full descriptor reconstruction remains.

This is not a full tile-record static pass. Two dynamic group-stride
multiply-by-1152 operations remain: one for the affine weight copy base and one
for the future affine weight-prefetch base. The unrolled prologue also contains
constant +1152/+2304 weight-base adds. A separate source candidate must replace
the two dynamic weight multipliers without reintroducing payload aliasing,
waits, sends, or descriptor construction. No timing is authorized.

## Preserved identities

- preregistration main-repo commit:
  `8262c6d3deccc6e2e1be3624f0f3fb082c62cb15`;
- candidate source commit:
  `86c1c8bdf75bbd84803f4d256b925b3f509e5ea4`;
- candidate base:
  `698113420380b3e343a04ab93321c7adf0b1e94e`;
- artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-affine-scale-clone-86c1c8bdf75b-20260803T020000`;
- analyzer report SHA-256:
  `95735eeb55c34d049c59bbaeb7b63dfe0c04111d950e11ea0d03d9ed714488f1`;
- selector-false assembly SHA-256:
  `5da07598487b4a964e379e91ad32ecd72887ca8895950bb97ecda1ec93e347eb`;
- selector-true assembly SHA-256:
  `612444c949d9d26bc0aa178561e6a651838e3910c9f367c35bdbae68d77be14c`.

The scale clone is the first affine-record successor to meet the numeric,
arithmetic, send, synchronization, GRF, and spill anchors simultaneously. Its
meaning is deliberately narrow: it validates deep payload cloning as a
source-level building block for the remaining weight-address work.

The 13.5-GiB/rank memory hard stop, device quarantine, and protected
125.461973 conventional tok/s record remain unchanged.
