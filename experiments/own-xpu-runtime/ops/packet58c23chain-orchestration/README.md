# Packet58-onecard-cache23-chain orchestration (ops/packet58c23chain-orchestration)

One-card record chain of the max23 capacity screen: packet182c-chain re-derived with the packet58-onecard-cache23
engine `083e3853…`, the `--cache-cap max23 --cache-bytes 23049601024` selection, the cache23 device plan (host
100,487,123,456 B) and the adapted submission validator. Packet: `stage2/packet58-onecard-cache23-chain` (its README
has the six-item table, the gate table and the launch/submission procedures). The directory name does not match the
pin guard's `ops/packet58-*` glob on purpose (DO-NOT-REPEAT).

## Tools in run order (CPU, `nice -n 19 taskset -c 8-15,24-31 python3 -B … </dev/null`)

| Step | Tool | Receipt |
| --- | --- | --- |
| 1 derive | `derive_cache23_chain.py` (generator `onecard_chain_derive.py` + packet182 repairs + capacity hook + prefix rule) | `derivation.json`, `capacity-patch.json`, `help.json`, `predevice-rehearsal.json`, `postnative-rehearsal.json`, `derivation-READY-FOR-DEVICE.json` (retired generator READY) |
| 2 delta | `apply_cache23_chain_delta.py` | `<packet>/evidence/cache23-chain-delta.json` |
| 3 gates a | `cpu_gates.py --phase a` (argument, parser, help, admission, engine, submission, drain, launch, python) | `<packet>/evidence/*.json` |
| 4 reseal | `reseal.py` | `reseal.json`, `<packet>/build-receipt.json`, `submission-pins.json`, `ready.json` |
| 5 gates b | `cpu_gates.py --phase b` (predevice, closure, postnative) then `reseal.py`, then `--step queue`, then `reseal.py` | `<packet>/evidence/{predevice,closure,postnative}-cache23.json`, `queue-gate.json`, `queue-plan.log` |
| 6 final | `final_checks.py` then `final_checks.py --ready` (READY written last; pin census; launcher rehearsal; verify_ready) | `<packet>/evidence/final-checks.json`, `final-pin-guard.json`, `launcher-rehearsal.json`, `READY-FOR-DEVICE.json` (packet + here), `ready.json` |
| check | `cpu_gates.py --check`, `verify_ready.py`, `admission_gate.py --verify` | – |

Reseal order after any edit to a sealed file: the affected gate(s) → `reseal.py` → `final_checks.py --ready` (withdraw
the READY files first: they are moved to `evidence/withdrawn-ready-<stamp>/` on any failure).

## Launch (coordinator, by hand; never automatic)

```bash
bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh --dry-run
bash experiments/own-xpu-runtime/ops/packet58c23chain-orchestration/launch_chain.sh
```

Refuses (rc 4) unless: the three owner endpoints are inactive; PAUSE-B present and PAUSE-A absent (archived by the
operator); no inflight/active-lane marker; no `lanequeue-*`/`window-*`/`packet58-onecard-cache23-a*` unit active and no
earlier `packet58-onecard-cache23-a` in a non-inactive state; every active `codex-*` unit frozen; `MemAvailable` ≥
101,560,865,280 B; root free ≥ 25,397,492,208 B; no `/dev/dri` client; the output `evidence/card0-cache23-a` and the
fault review absent; the final READY, `seal.py --verify`, `verify_ready.py` and the command digest agree; the fault
review captures exactly two known fault lines on this boot. It never creates, deletes or edits a PAUSE/STOP file and
never starts, stops or freezes any unit. Rehearsal overrides (`P58C23_LANE_DIR`, `P58C23_MEMINFO`, `P58C23_COORD_DIR`,
`P58C23_PROC`) force `--dry-run`. `entry-proposal.jsonl` is an entry-check descriptor for the pin guard and the
temporary lanequeue plan; never queue it.

Chain command (digest `354a08c87dce91ed4981b9a681942a5dd616cfa937363af2bb8c7cbbb0607e35`):

```
systemd-run --user --unit=packet58-onecard-cache23-a --property=Restart=no --property=SendSIGKILL=no --property=TimeoutStopSec=infinity --property=Nice=0 --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH=<recorded oneAPI path> OMP_NUM_THREADS=2 /usr/bin/python3 -B /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/queue_runner.py --authorized-device-window --card 0 --view down-tile16 --output-root /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/evidence/card0-cache23-a --fault-review /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23-chain/evidence/fault-review-cache23-a.json < /dev/null
```

Windows K1a → K1b → KD → W2m → WS → WS128x → WS128, 90 s gaps, ~35 min (packet182c chain: 09:47:31–10:20:52Z).

## Submission (after a finished, exact chain; see the packet README for the exact commands)

`prepare_submission.py --chain <output> --output <packet>/submission/prepared-a` → `submission.py --payloads … --dry-run`
→ coordinator: `--server-dry-run` → real submit → `prepare_submission.py --update-record <result.json> --submission-id <ID>`.
Receipts: `data/localmaxxing-responses/<date>-packet58-onecard-cache23-chain-a-onecard-ws128.txt` (key lines filtered).
Bars: WS128 > 35.92672010504166 (`cmvjejvoi03qcrf0138emu5a6`) and the live ledger; notes ≤ 2,000 chars; the 128-token
capped scope and the 21.55 → 23.05 GB capacity change are disclosed in the notes and the result packet.
