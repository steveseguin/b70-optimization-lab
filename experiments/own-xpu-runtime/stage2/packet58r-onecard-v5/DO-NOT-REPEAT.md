# Packet58r boundaries

| Arm or method | Status | Next condition |
| --- | --- | --- |
| Separate model load for each kernel-only A/B arm | Replaced here by one-load A/B/A/B/A | Keep separate loads for layout/allocation changes and later independent repeats. |
| route-fast / rec-both-plus over tile16 | CPU preparation; no device verdict | Coordinator's admitted whole-host card-0 gap and exact packet49 tokens in all views. |
| other-fusion selection on this one-card engine | Unavailable; rejected | Explicit port of packet109's missing kernels/dispatch plus new arithmetic gates. |

- Never change down layout, cache size, target weights, HC, card count or KV
  precision through the quiescent switch.
- Do not call zero uploads during a switch zero cache traffic after load.
  Preserve expert fills, host faults and every charged token; no cache drops,
  prompt warming, selective reruns or omitted slow views.
- Never pool repeated views into a fresh-process determinism or record claim.
  The 128-token screen has a false strict-final gate, even if every token matches.
- The full-shape mock does not copy device memory. Only that CPU mock supplies
  the clean error-readback word before a switch; the device still reads its
  actual sticky error and cannot clear it at a view boundary.
- Native/parser argument tests and full-size binding tests are separate gates.
  An intercepted launch does not prove real device arithmetic or speed.
- Cleanup proof is independent of experiment success. Never erase a fault,
  force a drain, kill another owner, or mark a failed screen passed to release it.
- All existing packets and ops remain frozen. Only the new proposal is for the
  coordinator; do not edit a live queue or auto-launch a record chain.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
