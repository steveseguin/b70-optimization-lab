# Laguna public-oneCCL prefix-24 row-0 model gate

Date: 2026-08-01 America/Toronto

Status: **completed PASS; non-scored model diagnostic only.** See
[`2026-08-01-public-oneccl-prefix24-row0-model-result.md`](2026-08-01-public-oneccl-prefix24-row0-model-result.md).

## Motivation

The standalone TP4 transaction A/B reproduced captured width-12 gather
corruption under installed oneCCL on 509–511 of 512 consumer replays per rank.
The pinned public 2022 runtime passed 512/512 on every rank with its exclusive
mapped hash. The model trace independently localized the known prefix-24
token-331 failure to the same layer-0 attention O-projection gather boundary.

## Matched arms

Use diagnostic vLLM
`3b68edc7501c546b03994ea8b6d6fa7bf23cc088`, protected XPU kernels
`99886d783372e621941228250091dc8ebdc1595d`, BF16 KV, exact width 12,
DFlash depth 11, and the current target/draft optimization stack.

Run exactly two fresh services with the checksum-pinned public oneCCL library
and matching kernels:

1. selector-off control, target topology `146/145`;
2. target inline-gather prefix 24, target topology `122/121`.

Both use the existing non-scored 2×400 smoke and one row-0 dump per rank at
position 420/input token 20253. The public runtime must be injected by
`LD_PRELOAD`, use the pinned `CCL_KERNEL_PATH`, and be the exclusive
`libccl.so` mapping in all four model workers. The harness records those maps.

## Gates

- The control must be 2/2 q1 exact, cache-zero, genuinely speculating, and
  preserve target `146/145` plus draft `14/13` on all ranks.
- The prefix-24 candidate must be 2/2 q1 exact, including removal of the known
  request-0 index-331 token `72` versus `372` failure, with target `122/121`
  plus draft `14/13` on all ranks.
- Both must produce four complete parity packets with matching scalar trigger
  identity and clean teardown.
- All candidate tensors through layer-0 local O projection must match the
  control as before. The layer-0 O-projection gathered output must now be
  bitwise equal to the control on ranks 0–3.

Any runtime/device error, incomplete map/packet set, topology drift, token
mismatch, or dirty teardown stops the experiment. Do not retry, reset, reload,
unbind, FLR, delete shared memory, or reboot.

## Decision rule

A complete pass authorizes a separately preregistered non-scored service-
lifetime gate. It does not authorize a score. A failure closes the pinned
public runtime for this direct captured-gather treatment unless the evidence
names a new, narrower runtime boundary. No `Work.wait()`, synchronization, or
model-math change is part of this treatment.
