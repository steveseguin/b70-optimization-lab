# Packet190: k3x two-card record chain (orchestration)

Packet190 is packet187's record chain (bundle 8 + packet153 static snapshot + packet186 V3 head placement, the
60.659520 tok/s record `cmvjvabyv040jrf01dricuz8s`) with packet189's **k3x** selection and engine. Exactly the six
items packet189's README ("Record bundle on a chain-rule win") prescribes changed from packet187:

1. **Selection** `k3x` (sha256 `c5443bbfbc88b39fd562956a55ce05667de0781f640fd0cd522a1e5800f392bb`, 19 keys) replaces
   V3 (`923639a9…`): `rank0_layers 0-26`, `boundary rank0-k3` (rank 0 runs GDN layers 24-26 for the verified token,
   rank 1 starts at QSA layer 27), `kernel_io kernel`, `rank0_prepare async`, `boundary_export copy`. Head, static
   snapshot, dense_scales and the draft are unchanged.
2. **Engines** packet189's device `87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4` and gnu-host
   `a50588a9e89adacb14cefcc53dd271cbd8054b81fe076dbca81d7b779d99f6c6`, byte copies of packet189 `v5/build`
   (`inputs/packet189-native.json`, packet copy `lineage-inputs/packet189-native.json`). No compile, no relink.
3. **Memory plan** packet189's k3x ledger (`97a7611646cdab0d9780166a3a670375a986dcb150cae491c686203eb0fb7d39`):
   rank 0 31,374,119,922 B (V3 + the 65 `blk.26.*` allocations), rank 1 31,581,735,626 B.
4. **Launcher host floor** `MemAvailable` ≥ 108,797,048,558 + 1,073,741,824 B.
5. **KD projection** the layer-streaming draft-capture reference projects `rank0_layers=0-23`, `boundary=none`,
   `snapshot_host=production` and **drops** `kernel_io`, `rank0_prepare`, `boundary_export` (k3-storage keys; the
   engine refuses them outside `rank0_layers=0-26`, so their production value is absence = copy/sync/copy).
6. **Bars** the chain's WS128 must exceed **60.659520** (`cmvjvabyv040jrf01dricuz8s`; ledger 60.65951991975228) and
   pass every exactness gate. `scripts/packet49_record_threshold.json` is the live threshold; `--update-record`
   appends after an approved submission.

Unchanged: the v5 transport size (266,304 B), the oracle binding, the lineage-inputs provenance layout, the launcher
refusals, the eleven windows and their argv, the submission step.

**Admission.** Coordinator ruling (2026-10-22): "Packet189 k3x met the chain rule on 2026-10-22 (lane B,
lanequeue-B36, 21:17–21:32 UTC): slower k3x view 62.225 ≥ 1.02 × every V3 view and ≥ 61.873. Derive the record bundle
from packet187 exactly as packet189's README prescribes and prepare a fresh eleven-window chain on cards 0+1; the
chain's WS128 must beat 60.659520 (cmvjvabyv040jrf01dricuz8s) and pass every exactness gate."
`bracket_gate.py` recomputes packet189's two lane-B rows and packet188's row 1 (the fresh V3 reference) from the raw
tokens, clocks and proposals; the 148 files it reads are pinned by sha256 where those packets retained them
(`evidence/bracket-gate.json`; READY carries the map's digest).

| View | Rate (tok/s) |
|---|---|
| k3x (row 1, one load) | 62.242, 62.225 |
| V3 in-load (k3 storage executed as V3) | 60.615, 60.444, 60.498 |
| V3 fresh (packet188 row 1, record selection, pinned `4ff1ec14…`) | 60.505 |

- The slower k3x view is +2.657 % over the fastest V3 view and above the 61.873 bar; V3 drift 0.283 %.
- Every view 13/13 exact (91 checks), identical proposals and acceptance, no kill rule fired.

This admits a chain, not a record. The scope is 128 tokens; strict512 and `realistic_final_gate` stay false.

## Chain windows and expected durations

Lane **A**, cards **0+1** (PCI 0000:23:00.0 / renderD130 and 0000:27:00.0 / renderD131). Output
`stage2/packet190-record-bundle-k3x/build/device-cards01-p190-a` (git-ignored `build/`), which must not exist yet.
Windows, argv and gaps (90 s) are packet136/187's. Expected durations are packet187's chain of 2026-10-22
(17:32:03–18:19 UTC, 11 windows); k3x decodes ~2.6 % faster, so the suite windows may be a few seconds shorter.

| Window | Purpose | Expected | Watchdog |
|---|---|---:|---:|
| K0 | JIT smoke, one process per card | 67 s | 600 s |
| K1a | kernel fixture checks (packet45 dispatch), first program | 89 s | 10,800 s |
| K1b | kernel fixture checks, second program | 87 s | 10,800 s |
| K2 | kernel class timing, which writes the measured dispatch used later | 366 s | 14,400 s |
| W0p | pipeline concurrency canary | 39 s | 600 s |
| KD | layer-streaming draft-capture reference (projected keys, above) | 166 s | 10,800 s |
| W2m | incident-retrospective, 64 tokens, two ranks, oracle-exact | 154 s | 10,800 s |
| WS | 12-prompt suite, 128 tokens, retains steps 1-8 | 223 s | 30,000 s |
| WSs | 12-prompt suite, 128 tokens, speed pair | 204 s | 30,000 s |
| WS128x | 128-token suite, retains steps 1-8 and 97-104 (exactness for WS128) | 237 s | 60,000 s |
| WS128 | **record window**: 128 tokens, no retention, class-balanced tok/s | 240 s | 60,000 s |

About **46-47 minutes** in all (1,872 s of windows + 900 s of gaps).

## Launch procedure (coordinator only, by hand)

Nothing has been queued, armed or launched.

1. **Bring the host to the admission state** (each a coordinator decision):
   - stop the three owner endpoints `qwen38-27b-fp8` (card 0), `qwen38-27b-fp8-tp1-test` (card 3),
     `qwen38-27b-vision` (cards 1+2);
   - archive `ops/lane-queue/PAUSE-A` out of the lane dir (the launcher only requires its absence);
   - **keep `PAUSE-B`**;
   - no lane job in flight; no other `window-*` or `lanequeue-*` unit active; freeze or stop `codex-*` units.
2. **Floors.** `MemAvailable` ≥ 109,870,790,382 B (108,797,048,558 + 1 GiB). Root free ≥ 28,324,718,708 B
   (25 GB + the chain's planned 3,324,718,708 B). At preparation time root free was ~28.4 GB: the margin is about
   100 MB, so free space first if anything else has been written (packet187's `build/device-cards01-p187-a`, 1.3 GB,
   is retained under `evidence/`, and packet189's 434 MB `run/` trees are tracked).
3. **Dry run:** `bash experiments/own-xpu-runtime/ops/packet190-orchestration/launch_chain.sh --dry-run`
   (every check incl. `verify_ready.py`; prints `dry run: every check passed; would run: systemd-run --user
   --unit=packet190-chain-a ...`).
4. **Launch:** `bash experiments/own-xpu-runtime/ops/packet190-orchestration/launch_chain.sh`. It repeats the
   checks, runs exactly `ready.json.chain_command` (below), waits at most 120 s for `packet190-chain-a` to become
   active and returns. It never retries.
5. **Watch:** `systemctl --user is-active packet190-chain-a`; `journalctl --user -u packet190-chain-a`;
   `<output>/queue-state.json` (`completed` grows window by window); `<output>/<W>/window.json`;
   `<output>/queue-all-complete.json` at the end; the launcher log `$FN/p190-launch.log`
   (default `/tmp/claude-1000/-home-steve/fn-run`).
6. **After the chain,** restoring PAUSE-A and the endpoints is the coordinator's decision. On a fault, follow the
   fault-halt rules. Nothing here resets, restarts or retries.

```bash
systemd-run --user --unit=packet190-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet190-orchestration/device-entry.sh chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/build/device-cards01-p190-a </dev/null
```

`device-entry.sh` reruns `verify_ready.py`, builds the closed library environment, enters `coordinator_windows.sh`
and `chain_entry.py queue`, which reruns `verify_cpu`/`verify_ready` before the windows. Each window keeps
packet136's lane admission, drain spacing, watchdogs and fault handling.

`launch_chain.sh` refuses (rc 4) when: an endpoint is active; PAUSE-B is absent or PAUSE-A present; an
`inflight-A/B.json` or `active-lane-A/B.json` marker exists; a `lanequeue-*`, `window-*` or `packet190-chain-a` unit
is active (the caller's own unit excluded); an earlier `packet190-chain-a` exists in any non-inactive state; memory
or disk is below the floor; the output exists; `verify_ready.py` fails or its command differs. It never creates or
deletes a PAUSE file and never starts or stops a service. `P190_LANE_DIR`, `P190_COORD_DIR`, `P190_MEMINFO` are
rehearsal-only overrides and force `--dry-run`. `proposal.jsonl` is an entry-check descriptor; never queue it.

## Submission (after a finished, exact chain)

```bash
# 1. Prepare the bundle. Read-only on the chain; never posts. Refuses unless WS128 is exact and > 60.659520.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet190-orchestration/prepare_submission.py \
  --chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/build/device-cards01-p190-a \
  --output experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/submission/prepared-a </dev/null
# 2. Local dry run: shared preflight plus the packet190 validator. No key, no network.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet190-orchestration/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/submission/prepared-a/payload-queue.json --dry-run </dev/null
# 3. Coordinator only: authenticated server dry run (LMX_API_KEY or the key file; never print it).
#    ...same command... --server-dry-run
# 4. Coordinator only: the real submit, with no flag. Receipts go to data/localmaxxing-responses/ with key lines filtered.
# 5. After an approved submission: append the record to scripts/packet49_record_threshold.json (improvement only).
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet190-orchestration/prepare_submission.py \
  --update-record experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x/submission/prepared-a/result.json --submission-id <ID> </dev/null
```

`evidence/submission-rehearsal.json` (CPU) covers the historical packet136 replay (refused by the current floor; a
tampered output refused), the k3x notes and flags on an in-memory relabel (1,508 of 2,000 chars: k3x, layers 24-26,
QSA layer 27, kernel_io/rank0_prepare/boundary_export, 60.659520, `cmvjvabyv040jrf01dricuz8s`, Packet189 screen,
strict512 false; `v3Boundary.rank0Layers 0-26`, `rank1FirstLayer 27`, `k3xTrims`), the local `--dry-run` path (a
foreign payload blocked, rc 2, no key, no network) and the record-update path on scratch ledgers (the real ledger
unchanged). `--server-dry-run` was **not** run: it needs the key (coordinator).

## CPU reproduction and gates

- CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`, at most 4 GiB; CPU work stops
  below 27 GB free. Poll `systemctl --user list-units 'window-*' 'lanequeue-*' 'packet18*' 'packet19*'` before any
  compile or heavy step (`compile_poll.py`).
- **Reseal order after any edit:** `place_k3x.py`, `select_k3x.py`, `guard_layout190.py` (packet side) →
  `cpu_bytes.py` → `preparation_probe.py` → `seal190.py` → the affected gates (`argument_gate.py`,
  `run_preparation.py`, `transport_gate.py`, `entry190.py`, `launch_limit_gate.py`, `drain_check.py`,
  `bracket_gate.py`, `chain_adapter.py check_inputs.py --report`, `make_proposal.py`, `rehearse_entry190.py --report`,
  `prepare_submission.py --rehearse-packet136`, the three unit tests) → `finalize190.py` → `final_checks.py --ready`,
  which writes READY **last** and reruns the pin guard and the launcher rehearsal; any failure withdraws READY.
- Gate receipts are in `evidence/`; `cpu-receipts.json` binds them; the packet README has the table.
- **Pin guard.** The live `ops/lane-queue/pin_guard.check_job` on `proposal.jsonl` finds 0 cross-packet mutable pins
  before and after READY (`evidence/final-checks.json`, `evidence/final-pin-guard.json`). Every ops file is pinned
  through its byte copy in `orchestration-snapshot/` and must equal that copy at launch.
- **Live-launch verification** (by `verify_cpu`/`verify_ready`, not by the guard): the ops code; the 148 packet189/188
  bracket files (`evidence/bracket-gate.json`); the four shared submission scripts (vendored in
  `lineage-inputs/dependencies/`).
- `evidence/packet136-chain-evidence.json.gz` (hard link of packet187's copy) is retained for the rehearsal. Parked
  helpers are in `lineage-p190-scaffolding/` and do not control admission.
