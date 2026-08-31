# Qwen3.8 Flash-Next TP4 event-chain A1 runtime negative

Date: 2026-08-31
Status: closed; candidate rejected

## Outcome

A1 did not reach a timing or correctness result. Replica 1 confirmed the
intended `Rt64_128_PCIE` protocol on all four ranks, completed the untimed
analytic receipt, and entered warmup. At the first measured-cycle
synchronization, all four ranks reported a device-lost runtime failure. The
frozen wrapper produced exit code 1, found no complete result, refused replica
2, and left no component process running.

This is a bounded negative for the **combined** clone-elision plus same-queue
event-chain candidate. It is not evidence against ordinary production XCCL,
and it cannot attribute the failure to one sub-mechanism. The candidate is
rejected; it receives no full-model endpoint arm and must not be retried merely
to obtain a timing number.

## Evidence and boundary

- Raw root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-event-chain-a1`.
- `torchrun.log` SHA-256:
  `fffc97505e1386983d160d69c38ad240b2fb13125ddb25a2f206bf37c4563a0b`.
- The four no-clobber Kineto traces have SHA-256 values recorded in the
  [structured result](../data/20260831-tp4-count2560-event-chain-a1-runtime-negative.json),
  and each contains the intended `Rt64_128_PCIE` kernel name.
- No checkpoint shard was read, no server was launched, no tok/s value was
  measured, and the accepted runtime was never modified.
- The protected MTP0 result remains `5.515783 tok/s`; the protected MTP4 result
  and all earlier evidence are unchanged.

## Host state

The failure reset all four device queues. All four cards still enumerate and
host memory/swap stayed healthy, but a tiny single-card compute postflight then
stalled on device 0 and was terminated. The current boot is therefore not
eligible for more GPU work. A reboot is required before the next GPU arm, but
none was performed because the operator may be away.

Continue with source review and preregistration only. After an attended reboot,
re-establish four-card compute/collective health and return to the accepted
runtime before testing a safer, separately frozen lever.
