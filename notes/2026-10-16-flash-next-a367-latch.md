# Flash-Next A367 prior-boot latch exemption — 2026-10-16

The owner's October 16 “Exempt prior-boot evidence” decision is implemented in
the shared driver admission check and A367 calibration. Only a different boot
and an exact `fault-archive`, `evidence`, or `incident` directory segment below
a watched root qualify. Top-level latches, current-boot latches, missing or
unreadable boot IDs, and ordinary run paths still block. The packet
[README](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/README.md#owner-decision-exempt-prior-boot-evidence-2026-10-16)
records the owner's full decision. No boot identity is hardcoded.

Both admission passes save exempted paths, SHA256 hashes and boot IDs in
`admission.json`. Its hash is recorded in `environment.json`, which is bound
by the run identity. The shared fixture driver now uses the same nested
admission scan. The existing live top-level latch and kernel checks remain
strict. No model, device, service, power, memory, swap or reboot action ran.
Existing FAULT files, protected source and rescue archive were not changed.

## Validation

- [CPU suites](../data/2026-10-16-flash-next-a367-latch/cpu-tests.json): 145 passed, zero failures/errors/skips — 71 calibration, 59 driver, six payload helper and nine frozen-tree verifier. New latch tests use virtual files. They cover all five requested cases, unreadable/malformed IDs, exact path segments, nested roots, output-root blocking, de-duplication, new boot identity, discovery, and persistence of both admission receipts. The existing suites use their temporary synthetic fault fixtures.
- [Read-only live-path audit](../data/2026-10-16-flash-next-a367-latch/latch-audit.json): exactly the two named latches qualify on boot `13858eef-ec68-44ea-a67c-9444933b7100`, both from `4aafe57b-a54f-4bfd-b4ed-9f1cbb8830c7`. This classifies latches only; it supplies no launch or health approval.
- [Seal audit](../data/2026-10-16-flash-next-a367-latch/seal-audit.json): zero mismatches in 16 calibration seal members, nine driver seal members and 93 calibration dependencies. The two previously blocked fixture inputs remain unchanged and unapproved.
- [Runbook syntax](../data/2026-10-16-flash-next-a367-latch/runbook-check.json): seven shell blocks and two Python heredocs checked without execution. The runbook reads hashes and boot ID dynamically and now describes the exemption, admission receipt and coordinator approval recording.

## Seals and pending approval

- `calibration_seal`: `a15e5223b2f5a9fe0476db6a79ee1aabd06d161e3a6c58ef1dd5e5e6d67b7764`
- `driver_seal`: `e29fe31176a529879642e0e8bfea45e2266359304374d7d770c18e9129463c7a`
- `calibration_preregistration`: `0c1c5cbeda393c2d6d1f1699699d936793cd4c3449dff6eedbdfa5b60ce66c0a`
- `driver_preregistration`: `db83805e9a2b4099a0f6bdb005d0d08310009d474ce62546356f3c505e9f65b9`

The owner has already approved the 114,000,000 KiB exception. The regenerated
[pending object](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/owner-approval.pending.json)
stays `approved=false`. The coordinator will record that approval against the
new hash using the owner's verbatim words. The exact new sentence is:

> I authorize one A367 calibrate-load measurement on steve-b70s with a calibration-only MemAvailable start floor of 114000000 KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 0c1c5cbeda393c2d6d1f1699699d936793cd4c3449dff6eedbdfa5b60ce66c0a and seal SHA256 a15e5223b2f5a9fe0476db6a79ee1aabd06d161e3a6c58ef1dd5e5e6d67b7764. This accepts the unmatched loading-memory risk, does not lower the packet-4 fixture floor, and does not resolve the halt or authorize another launch.

The owner/coordinator's reboot follows this handoff. No pre-reboot window or
health receipt admits the new boot. Follow the updated
[launch runbook](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/LAUNCH-RUNBOOK.md)
with current storage, boot, health, ownership, payload and hash-bound approval.
This CPU repair does not authorize execution or another launch.

Repeat the CPU suites under the required scheduling limits:

```bash
taskset -c 4-15,20-31 nice -n 19 ionice -c 3 python3 -B data/2026-10-16-flash-next-a367-latch/run-cpu-tests.py
```
