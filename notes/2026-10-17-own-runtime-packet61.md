# Packet61 — controller spin plus HC fusion

October 17, 2026. CPU preparation on steve-b70s is complete. The combined
candidate is built and sealed; the coordinator can run its screen and full
chain. No GPU or service ran in this task, and no packet61 speed is claimed.

Packet61 keeps packet56w's 250 µs spin and rank-0 queue profiling property and
uses packet60's exact three HC kernels on both target sides, including both
serial M=2 rows. The draft prefix remains 91,392 rows. The full target, BF16
intermediates, BF16 KV and packet49 oracle are unchanged. Kernel sources and
reused HC object bytes are identical to packet60; the controller and device
wait sources are identical to packet56w.

Both builds pass. The CPU checks match 878,040 HC bytes, all 96 target fixtures
and 24 tokens against packet56. All 1,123 controller cases, five mailbox fault
cases and 31 chain/submission checks pass. Screen v1 and v3 both accept the
seal. The full chain plan verifies the oracle and the two parent prefix
windows. Storage passed with about 4.65 GB above its required reserve; the
coordinator must recheck before launch.

The build uses about 143 MB logically, about 108 MiB allocated with hardlinks,
below the 400 MB cap. Packet56x was not sealed when integration began around
15:15 UTC, so its later wait variants are left out. `wait-option.json` records
a clean extension point and keeps packet56w waits fixed. No shared screen,
packet56x, cleanup, CURRENT.md or sealed parent file was edited; the explicit
own-folder scope takes precedence for this handoff, apart from this requested
note. The initial pull rebased main successfully; later concurrent main
commits remain intact.

The submission helper reads `scripts/packet49_record_threshold.json` and
requires a rate above its current floor, 46.96269702286488 tok/s at preparation.
Payload notes name the prefix, spin/queue property and HC fusion. A full chain
is still required. The 128-token scope remains explicit and the strict
512-token gate remains false. No dry-run, API call or submission was sent.

The initial compile failures were local harness issues: a missing `.inc`
copy, colliding object basenames and two checked-header trees included in the
same fixture. They were corrected before sealing. The passing fixtures and
commands are retained in the packet, along with its CPU closeout.

- [Packet and all receipts](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/README.md)
- [Exact screen and chain commands](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/WINDOW.md)
- [Submission commands](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/SUBMISSION.md)
- [CPU closeout](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/CPU-PREPARATION-CLOSEOUT.md)


## Packet61x — pure-spin waits, October 17 CPU preparation

Packet61x is built, sealed and ready for coordinator device windows. Its hook
required a minimal host rebuild in
`experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/`.
All covered waits now use packet56x variant (a): pure PAUSE spin with yield
every 256 iterations, including mailbox, device completion and pending-draft
progress waits. Deadlines, cancellation, peer abort and callbacks remain.
No parent packet was edited.

The embedded kernel bundle is byte-identical to packet61: 5,355,244 bytes,
SHA256 `14e449bbcefbf8e076c8ddcb2c477460117b6db3a6075361e44b46c4e8b41afe`.
All 71 reused link objects are unchanged hardlinks. The final device binary is
`c846812c97251df126152f7584bfca301771f3ec404f3dba42d5edf6808c0f49`.
Both builds pass. All 1,123 controller cases, seven wait checks, five mailbox
fault checks and 33 chain/submission tests pass. Target fixtures match packet56
exactly: 96 fixtures and 24 tokens; HC fixture equality covers 878,040 bytes.
The screen seal is accepted by v3 plans on both lanes. Full-chain admission,
shared oracle, parent prefix windows, output registration and submission pins
pass. The current floor remains dynamically checked; the strict 512-token gate
remains false for the owner-scoped 128-token chain.

No GPU, model load, service, sudo, setting change or external submission ran.
CPU work used nice19, cores 8–15 and 24–31, and Python `-B`. Build retention is
about 108 MB logically. Storage passed with 4.45 GB above its required reserve;
launch must recheck. The initial build finalization found a stale primitive
sub-receipt hash; using packet61's verified final build receipt resolved it.
The system Python lacked pytest, so tests used the existing venv without any
installation. Device quality and speed remain pending; the v1 gains are not
assumed additive.

[CPU closeout](../experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/CPU-PREPARATION-CLOSEOUT.md),
[kernel byte proof](../experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/evidence/kernel-bundle-identity.json),
[submission commands](../experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/SUBMISSION.md).

### Exact coordinator commands

These device commands were not executed. Run each v3 lane in its own admitted
nice0 `screen-*` unit, using the coordinator's approved library path and a
fresh reviewed fault receipt. The full chain requires its own exclusive
admission. Both screen and chain use the identical sealed 61x executable.

Lane A, physical cards 0+1:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
V=experiments/own-xpu-runtime/stage2/screen/v3
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P" --seal "$P/screen-seal.json" \
  --binary "$P/build/device/own-rt-iq3" --dispatch "$P/dispatch-speed6.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet61x-A-01"
```

Lane B, physical cards 2+3:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
V=experiments/own-xpu-runtime/stage2/screen/v3
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P" --seal "$P/screen-seal.json" \
  --binary "$P/build/device/own-rt-iq3" --dispatch "$P/dispatch-speed6.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet61x-B-01"
```

Full chain, physical cards 0+1, inside the admitted nice0 unit on cores 0–3,16–19 with `OMP_NUM_THREADS=2`:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
HEAD=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$HEAD/evidence/head-k-a/window.json" "$HEAD/evidence/head-k-b/window.json"
```

The chain is K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128. [All CPU preflight and plan commands](../experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/WINDOW.md) are retained beside the packet.
