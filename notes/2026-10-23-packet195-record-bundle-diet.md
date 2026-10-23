# 2026-10-23: packet195, two-card k3x-diet record bundle, CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/`](../experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/README.md).
Orchestration: [`experiments/own-xpu-runtime/ops/packet195-orchestration/`](../experiments/own-xpu-runtime/ops/packet195-orchestration/README.md).

No GPU, `/dev/dri`, device binary run, systemd unit, PAUSE/STOP or queue file, sudo or secret was touched. Nothing was queued, armed,
submitted or committed; no tracked file outside the two new directories and this note was edited (packet190/193/194 untouched). The only
systemd reads were `list-units`/`show`/`is-active` queries: the unit poll before the compile and heavy steps (`compile_poll.py`, 06:27:01Z: no
`window-*`, `lanequeue-*`, `packet*` unit active; the owner's endpoint-restore `window-p194b-driver …-restore21` had ended and such windows
are tolerated by the poll) and the launcher's live `--dry-run`. Everything ran under `nice -n 19 taskset -c 8-15,24-31`, one compiler at a time
through the shared compile lock (the one-card CPU preparation ran concurrently on the host).

## Why

Packet194's two lane-B rows (lanequeue-B40, 05:56-06:11 UTC) made the exp-diet a screen winner (`s194_decision`):

| Row | Views |
|---|---|
| k3x-diet smoke (12 × 64 + incident64) | 63.115 tok/s, 13/13 exact, data proof passed |
| one load k3x / k3x-diet / k3x / k3x-diet / k3x (12 × 128 + incident64 each) | k3x-diet 63.474 and 63.413; k3x 62.168, 62.155, 62.193 |

* The slower k3x-diet view is +1.962 % over the fastest k3x view; k3x drift 0.061 %; gate/up saving 10.8 (rank 0) / 11.8 (rank 1) µs per
  layer from the host scopes; every view 13/13 exact with identical proposals and acceptance; no kill rule fired.
* The chain rule (≥ +2 % over every k3x view and ≥ 63.592 tok/s) is missed by 0.04 points.

Coordinator ruling (quoted): "packet194 k3x-diet is a screen winner on 2026-10-23 (lane B, lanequeue-B40, 05:56–06:11 UTC): +1.96 % over
every k3x view, every view exact; the +2 % chain bar is missed by 0.04 points, and the lanes are idle, which the chain policy allows. Derive the
record bundle from packet190 with the `k3x-diet` selection and packet194's engine; prepare a fresh eleven-window chain on cards 0+1; its WS128
must beat 62.345282 (cmvk51wfn001gng01fpbfy89q) and pass every exactness gate."

## What packet195 is

Packet190's record harness (bundle 8 + packet153 static snapshot + V3 head placement + packet189 k3x; the 62.345282 record) copied by
`copy_packet195.py` (identity rewrites only, receipt `lineage/packet195-copy.json`: 938 + 83 files, 26 + 37 rewritten) with exactly the six
changes of packet194's README:

1. **Selection** k3x-diet `eb417ec915821def1ccfa9ecaf87851ee81846097d489ba52196f63d551a50ac` (20 keys = packet189's k3x `c5443bbf…` +
   `expert_gateup diet`): the exp-halfcache (IQ2_S) gate/up launches use packet193's exact instruction diet `p193diet::GateUp` (26 sites on
   rank 0, 24 on rank 1; the IQ3_S p28 layer keeps its kernel). Bit-identical to `p90exp::Kernel<IQ2_S,2560,64,false,true>` on both host
   twins, in the random stress and on device. Everything else unchanged.
2. **Engines** packet194's device `b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc` and gnu-host `5d8f3c05…`, byte copies of
   packet194 `v5/build` (`inputs/packet194-native.json`; packet194 built them with 10 compiler runs, 0 warnings, pinned header `aab37609…`);
   packet195 ran 0 compiler runs for them. `diet-native/` snapshots packet194's native sources and the `p194-native.patch`.
3. **Memory plan** unchanged: packet188/189's k3 ledger `97a76116…`, rank 0 31,374,119,922 B, rank 1 31,581,735,626 B; the diet adds 0 B per
   rank (packet194 census, reproduced by packet195's real-shape run).
4. **Launcher host floor** unchanged: 108,797,048,558 B + 1 GiB (`MemAvailable` ≥ 109,870,790,382 B).
5. **KD projection** the layer-streaming reference drops `expert_gateup` together with `kernel_io`, `rank0_prepare`, `boundary_export` (k3-storage
   keys the engine refuses outside the k3 storage; absence = production) and `rank0_layers=0-23`, `boundary=none`, `snapshot_host=production`.
6. **Bars** WS128 > 62.345282 (`cmvk51wfn001gng01fpbfy89q`; ledger 62.345281904743764, the rounded figure is the hard floor);
   `scripts/packet49_record_threshold.json` untouched until an approved submission.

Unchanged: the 266,304 B transport, the oracle binding, the provenance layout, the launcher guards (endpoints stopped, PAUSE-A absent,
PAUSE-B present, no lane marker or competing unit, memory and disk floors, fresh output, `verify_ready`), unit `packet195-chain-a`, 120 s
deadline, no retry.

## Results (CPU)

* **Startup.** Production-shape startup of both ranks with the k3x-diet selection (every view re-selecting the diet): census 31,374,119,922 /
  31,581,735,626 B, 90 moved sites on rank 0, image 19,025,640 B / 984 extents, 23 native refusals, diet at 26 / 24 sites, captures equal
  packet194's diet-first load and differ from the production k3x capture.
* **State.** The k3x-diet state engines (GNU, Intel) reproduce packet194/189/188's canonical transcript `d451302d…` with copy-engine export only;
  the diet is inert and counted in the miniature (no exp-halfcache layout).
* **Transport.** The W0p canary passes 1000 handovers through the chain code, the old size fails, and the k3x-diet five-layer miniature decode
  equals bundle 8 (120 fixtures, 28 boundaries).
* **Entry.** All 11 window entries pass; the both-rank preparation probe loads the real WS128 argv (device totals = the census).
* **Admission.** s194 recomputed from raw rows (126 files pinned in place): slower k3x-diet 63.4128, +1.962 %, drift 0.061 %, saving 10.79 µs/layer;
  `chain_rule_met=false` (shortfall 0.038 points), admitted through `policy195.json` `coordinator_idle_lane_exception_authorized` only.
* **Submission rehearsal.** Notes 1,726 of 2,000 chars (128-token capped scope and the bit-identical diet kernel disclosed; engine flag
  `expertGateUp`); the 62.345282 floor refuses packet136's replay; the local `--dry-run` blocks a foreign payload with no key; the record update
  refuses a non-improving result and appends on a scratch ledger; `--server-dry-run` left to the coordinator.
* **Pin guard and plan.** 923 pins, 0 cross-packet mutable; private `lanequeue.py plan --lane A` rc 0; launcher rehearsal 1 pass + 9 refusals.
* **Fixed on the way** (harness shape, not arithmetic): the packet `evidence/` dir must exist before the seal; `seal195.py` must run again after
  `make_proposal.py` (the snapshot pins `proposal.jsonl`); `real_report.py` replays packet190's record chain (packet136's output was archived
  off the root disk on 2026-10-22) and must reproduce 62.345281904743764.

## Expected chain time

Packet187's windows (K0 67 s, K1a 89, K1b 87, K2 366, W0p 39, KD 166, W2m 154, WS 223, WSs 204, WS128x 237, WS128 240; 1,872 s plus
10 × 90 s of gaps), about **46-47 min**; packet190's chain took 47 min (22:06-22:53 UTC). The diet decodes ~2 % faster.

## Next

1. The coordinator stops the three endpoints, archives PAUSE-A, keeps PAUSE-B; root free must stay ≥ 28,324,718,708 B (30.9 GB at seal time;
   keep packet190's `build/device-cards01-p190-a`, it is an input of the report rehearsal).
2. `bash experiments/own-xpu-runtime/ops/packet195-orchestration/launch_chain.sh --dry-run`, then without the flag.
3. If WS128 is exact and above 62.345282: `prepare_submission.py --chain … --output …/submission/prepared-a`, `submission.py --payloads
   …/payload-queue.json --dry-run`, `--server-dry-run`, the real submit, `prepare_submission.py --update-record … --submission-id <ID>`;
   receipts to `data/localmaxxing-responses/` with key lines filtered. On a loss or fault: record the window and the DO-NOT-REPEAT row; the
   record stays at 62.345282.
