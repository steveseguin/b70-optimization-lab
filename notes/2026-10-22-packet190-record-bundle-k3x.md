# 2026-10-22: packet190, two-card k3x record bundle, CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/`](../experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/README.md).
Orchestration: [`experiments/own-xpu-runtime/ops/packet190-orchestration/`](../experiments/own-xpu-runtime/ops/packet190-orchestration/README.md).

No GPU, `/dev/dri`, device binary run, systemd unit, PAUSE/STOP or queue file was touched. Nothing was queued, armed, submitted or committed.
The only systemd reads were `list-units`/`is-active` queries: the unit poll before the compile and heavy steps (`compile_poll.py`,
21:49:24Z: no `window-*`, `lanequeue-*`, `packet18*`, `packet19*` unit active; the coordinator's `window-p189-driver` had ended at
21:41Z with the three endpoints restored) and the launcher's live `--dry-run`.

## Why

Packet189's two lane-B rows (lanequeue-B36, 21:17-21:32 UTC) met the +2% record-chain rule (`s189_decision`):

| Row | Views |
|---|---|
| k3x bracket (one load V3/k3x/V3/k3x/V3) | k3x 62.242 and 62.225 tok/s; in-load V3 60.615, 60.444, 60.498 |
| Fresh V3 reference (packet188 row 1, record selection) | 60.505 |

* The slower k3x view is +2.657% over the fastest V3 view and clears the 61.873 tok/s bar (1.02 × 60.659520).
* Every view is 13/13 exact, with identical proposals and acceptance; V3 drift 0.28%; no kill rule fired.

Coordinator ruling (quoted): "Packet189 k3x met the chain rule on 2026-10-22 (lane B, lanequeue-B36, 21:17–21:32 UTC): slower k3x view
62.225 ≥ 1.02 × every V3 view and ≥ 61.873. Derive the record bundle from packet187 exactly as packet189's README prescribes and prepare a
fresh eleven-window chain on cards 0+1; the chain's WS128 must beat 60.659520 (cmvjvabyv040jrf01dricuz8s) and pass every exactness gate."

## What packet190 is

Packet187's record harness (bundle 8 + packet153 static snapshot + V3 head placement; the 60.659520 record) copied by `copy_packet190.py`
(identity rewrites only, receipt `lineage/packet190-copy.json`) with exactly the six changes of packet189's README:

1. **Selection** k3x `c5443bbf…` (19 keys): `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io kernel`, `rank0_prepare async`,
   `boundary_export copy`; head, static snapshot, dense_scales and draft unchanged.
2. **Engines** packet189's device `87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4` and gnu-host `a50588a9…`, byte copies
   of packet189 `v5/build` (`inputs/packet189-native.json`); no compile, no relink.
3. **Memory plan** packet189's k3x ledger `97a76116…`: rank 0 31,374,119,922 B.
4. **Launcher host floor** 108,797,048,558 B + 1 GiB (`MemAvailable` ≥ 109,870,790,382 B).
5. **KD projection** the layer-streaming reference drops `kernel_io`, `rank0_prepare`, `boundary_export` (the engine refuses them outside the
   k3 storage; absence = the production path) together with `rank0_layers=0-23`, `boundary=none`, `snapshot_host=production`.
6. **Bars** WS128 > 60.659520 (`cmvjvabyv040jrf01dricuz8s`); `scripts/packet49_record_threshold.json` untouched until an approved submission.

Unchanged: the 266,304 B transport, the oracle binding, the provenance layout, the launcher guards (endpoints stopped, PAUSE-A absent,
PAUSE-B present, no lane marker or competing unit, memory and disk floors, fresh output, `verify_ready`), unit `packet190-chain-a`, 120 s
deadline, no retry.

## Results (CPU)

* **Startup.** Production-shape startup of both ranks with the k3x selection: census 31,374,119,922 / 31,581,735,626 B, 90 moved sites
  on rank 0, image 19,025,640 B / 984 extents, captures equal packet189's k3x-first.
* **State.** The k3x state engines (GNU, Intel) reproduce packet189/188's canonical transcript `d451302d…` with copy-engine export only.
* **Transport.** The W0p canary passes 1000 handovers through the chain code, the old size fails, and the k3x five-layer miniature decode
  equals bundle 8 (120 fixtures, 28 boundaries).
* **Entry.** All 11 window entries pass; the both-rank preparation probe loads the real WS128 argv (device totals = the census).
* **Admission.** s189 recomputed from raw rows (148 files pinned in place): slower k3x 62.2254, +2.657%, drift 0.283%.
* **Submission rehearsal.** Notes 1,508 of 2,000 chars; the 60.659520 floor refuses packet136's replay; the local `--dry-run` blocks a foreign
  payload with no key; the record update refuses a non-improving result and appends on a scratch ledger; `--server-dry-run` left to the coordinator.
* **Pin guard and plan.** 920 pins, 0 cross-packet mutable; private `lanequeue.py plan --lane A` rc 0; launcher rehearsal 1 pass + 9 refusals.
* **Fixed on the way** (harness shape, not arithmetic): `build_engine.limits()` counted the guard-layout hard links; the four-layer chain
  miniature cannot host `0-26` (five-layer `--pipeline-mini5` for reference and k3x); the hard floor is the rounded 60.659520, 8e-8 above
  the ledger value.

## Expected chain time

Packet187's chain of 2026-10-22 (17:32-18:19 UTC): K0 67 s, K1a 89, K1b 87, K2 366, W0p 39, KD 166, W2m 154, WS 223, WSs 204, WS128x 237,
WS128 240; 1,872 s plus 10 × 90 s of gaps, about **46-47 min**. k3x decodes ~2.6% faster.

## Next

1. The coordinator stops the three endpoints, archives PAUSE-A, keeps PAUSE-B, and frees disk if root free is below 28,324,718,708 B
   (28.35 GB at seal time; margin ~30-100 MB).
2. `bash experiments/own-xpu-runtime/ops/packet190-orchestration/launch_chain.sh --dry-run`, then without the flag.
3. If WS128 is exact and above 60.659520: `prepare_submission.py --chain … --output …/submission/prepared-a`, `submission.py --payloads
   …/payload-queue.json --dry-run`, `--server-dry-run`, the real submit, `prepare_submission.py --update-record … --submission-id <ID>`;
   receipts to `data/localmaxxing-responses/` with key lines filtered.

## Device result and submission (2026-10-22, chain 22:06-22:53 UTC, unit packet190-chain-a): NEW RECORD 62.345282 tok/s, APPROVED

All eleven windows passed on cards 0+1 (K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, WS128x, WS128), no kernel faults. WS128: **62.345282 tok/s**
class-balanced (median of prompt-class medians; all-prompt median 62.264891, p10 60.21; class medians analysis 62.21, code 61.96, documentation 64.17,
operations 62.32, prose 62.37, structured-writing 63.29), 12/12 prompts and 1,536 tokens exact vs `iq3-p49-split32-v1`, timing-claim eligible;
TTFT median 912 ms, wall rate 43.16 tok/s, acceptance 0.787, hit/miss cycle 13.53/25.56 ms (packet187: 14.07/25.78).

`prepare_submission.py --chain … --output submission/prepared-a` (run under `taskset -c 4-15,20-31`; the tool refuses the reserved cores) ->
`submission.py --dry-run` (passed) -> `--server-dry-run` HTTP 200 `{"valid": true}` -> real submit **HTTP 201, run `cmvk51wfn001gng01fpbfy89q`, APPROVED**
(+2.78 % over `cmvjvabyv040jrf01dricuz8s` 60.659520) -> `--update-record` (threshold file now 62.345281904743764, result sha `afc68ab5…`). Receipt
`data/localmaxxing-responses/2026-10-22-packet190-record-bundle-k3x-ws128.txt`. The prepared `ledger-entry.md`/`result-packet.md` say "pending"
(written before the submission); the submissions ledger and threshold file carry the id.

Host: endpoints idle since the restore13 validations (21:40 UTC); root disk 25 MB above the launcher floor before the chain, so packet97/103 closed
chain outputs were archived to the USB model disk with sha256 manifests (`stage2/DISK-CLEANUP-20261022.md`), margin 3.28 GB at launch; endpoints
restored afterwards as `*-20261022-restore14`; PAUSE-A re-armed, PAUSE-B untouched. Window receipts: `lineage/window-20261022/` in the packet.
