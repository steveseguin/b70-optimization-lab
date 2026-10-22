# 2026-10-22: packet187, two-card V3 record bundle, CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/`](../experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/README.md).
Orchestration: [`experiments/own-xpu-runtime/ops/packet187-orchestration/`](../experiments/own-xpu-runtime/ops/packet187-orchestration/README.md).

No GPU, `/dev/dri`, device binary run, systemd unit, PAUSE/STOP or queue file was touched. Nothing was queued, armed, submitted or committed.
The only systemd reads were `is-active`/`list-units` queries:

* `compile_poll.py` (window-p186-driver: active until 16:44Z, inactive at 16:45Z);
* the launcher's live `--dry-run`.

## Why

Packet186's four lane-B rows met the +2% record-chain rule (`s186_decision`):

| Row | Views |
|---|---|
| V3 bracket | 60.573 and 60.533 tok/s |
| Split-head controls | 58.595 and 58.441 |
| U | 57.832, 57.802 and 57.840 |

* The slower V3 view is +3.306% over the faster split control and +4.66% over the un-split views.
* It clears the 59.974 tok/s bar.
* Every view is exact, with identical proposals and acceptance.

The coordinator's ruling was to prepare the record bundle.

## What packet187 is

* The selection, plan, dispatch and engines are packet186's V3 arm, byte for byte:
  * selection `923639a9…`;
  * device engine `693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739`, reused, no relink, 0 compiler runs.
* The chain is packet136's eleven-window lane-A chain on cards 0+1 with three changes:
  1. **Transport size.** The chain transport file is the v5 engine's 266,304 B. This closes packet155's W0p `shared extent` failure.
  2. **KD.** KD's layer-streaming reference projects the V3 keys to production.
  3. **Provenance layout.** Inherited provenance moved under `lineage-inputs/` (packet143 layout), so the live pin guard sees 0 cross-packet mutable pins (3,925 before).
* The guarded launcher `launch_chain.sh` follows packet182's p182-win pattern.
  * It refuses when any of these is true:
    * an endpoint is active;
    * PAUSE-B is missing, or PAUSE-A is present;
    * a lane marker or a competing unit exists;
    * memory is below 107,667,817,956 B + 1 GiB;
    * disk is below 25 GB + 3,324,718,708 B;
    * the output already exists;
    * `verify_ready` fails.
  * It launches only the `ready.json.chain_command` unit `packet187-chain-a`, with a 120 s deadline and no retry.

## Expected chain time

These durations are from packet136's record chain, 2026-10-18 16:55:53-17:42:05Z:

| Window | K0 | K1a | K1b | K2 | W0p | KD | W2m | WS | WSs | WS128x | WS128 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Seconds | 67 | 89 | 87 | 366 | 39 | 166 | 154 | 223 | 204 | 237 | 240 |

The windows take 1,872 s, plus 10 × 90 s of gaps, for about **46-47 min**.

## Results (CPU)

* **Startup.** The production-shape startup of both ranks equals packet186's V3 census: 30,245,049,064 and 31,581,735,626 B.
* **Transport.** The W0p canary passes 1000 handovers through the chain code, the old size fails, and the V3 miniature decode equals bundle 8.
* **Entry.** All 11 window entries pass, and the s186 screen was recomputed from raw rows.
* **Submission rehearsal.**
  * The notes are 1,171 of 2,000 chars.
  * Packet136 replay is refused by the floor.
  * Local `--dry-run` blocks a foreign payload with no key and no network.
  * The record update refuses a non-improving result and appends on a scratch ledger.
  * `--server-dry-run` was left to the coordinator.
* **Pin guard and plan.** The pin guard finds 0 cross-packet mutable pins, and the private `lanequeue.py plan --lane A` gives rc 0.

## Next

1. The coordinator stops the three endpoints, archives PAUSE-A and keeps PAUSE-B.
2. Run `launch_chain.sh --dry-run`, then `launch_chain.sh`.
3. If WS128 is exact and above 58.798109, submit:
   1. `prepare_submission.py --chain …`;
   2. `submission.py --dry-run`;
   3. `--server-dry-run`;
   4. the real submit;
   5. `--update-record`.
