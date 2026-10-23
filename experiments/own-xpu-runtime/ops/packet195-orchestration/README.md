# Packet195: k3x-diet two-card record chain (orchestration)

Packet195 is packet190's record chain (bundle 8 + packet153 static snapshot + packet186 V3 head placement + packet189 k3x,
the 62.345282 tok/s record `cmvk51wfn001gng01fpbfy89q`) with packet194's **k3x-diet** selection and engine. Exactly the six
items packet194's README ("Record bundle on a chain-rule win (derive from packet190)") prescribes changed from packet190:

1. **Selection** `k3x-diet` (sha256 `eb417ec915821def1ccfa9ecaf87851ee81846097d489ba52196f63d551a50ac`, 20 keys) replaces
   k3x (`c5443bbf…`, 19 keys): the one changed key is `expert_gateup diet`. The exp-halfcache (IQ2_S) gate/up launches use
   packet193's exact instruction diet `p193diet::GateUp` instead of `p90exp::Kernel<IQ2_S,2560,64,false,true>` (26 sites on
   rank 0, 24 on rank 1; the IQ3_S p28 gate/up layer on rank 0 keeps its kernel). Everything else (head, static snapshot,
   k3 boundary, trims, export path, dense_scales, draft) is packet190's. The explicit `production` form (`c20504b7…`,
   packet194's bracket control) is the same engine path as packet190's 19-key record selection (packet194 full-shape gate).
2. **Engines** packet194's device `b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc` and gnu-host
   `5d8f3c057ccbe2214da30bbf98f656f23d63653db328c64102cfdf59425720db`, byte copies of packet194 `v5/build`
   (`inputs/packet194-native.json`, packet copy `lineage-inputs/packet194-native.json`). No compile, no relink; 0 compiler
   runs for the engines (the only compile was the CPU preparation probe).
3. **Memory plan** unchanged: packet188/189's k3 ledger (`97a7611646cdab0d9780166a3a670375a986dcb150cae491c686203eb0fb7d39`),
   rank 0 31,374,119,922 B, rank 1 31,581,735,626 B. packet194's full-shape census: the diet adds **0 B per rank**;
   packet195's own real-shape run reproduces the census with the diet at every exp-halfcache gate/up site.
4. **Launcher host floor** unchanged: `MemAvailable` ≥ 108,797,048,558 + 1,073,741,824 B.
5. **KD projection** the layer-streaming draft-capture reference projects `rank0_layers=0-23`, `boundary=none`,
   `snapshot_host=production` and **drops** `kernel_io`, `rank0_prepare`, `boundary_export` **and `expert_gateup`**
   (k3-storage keys; packet194's engine refuses them outside `rank0_layers=0-26`, so their production value is absence:
   copy/sync/copy/the record gate/up kernel). The reference selection keeps 16 keys; the diet moves no byte.
6. **Bars** the chain's WS128 must exceed **62.345282** (`cmvk51wfn001gng01fpbfy89q`; ledger 62.345281904743764, the
   rounded figure is 9.5e-8 above it and is the hard floor) and pass every exactness gate. `scripts/packet49_record_threshold.json`
   is the live threshold; `--update-record` appends after an approved submission.

Unchanged: the v5 transport size (266,304 B), the oracle binding, the lineage-inputs provenance layout, the launcher
refusals, the eleven windows and their argv, the submission step.

**Admission.** Coordinator ruling (2026-10-23, quoted): "packet194 k3x-diet is a screen winner on 2026-10-23 (lane B,
lanequeue-B40, 05:56–06:11 UTC): +1.96 % over every k3x view, every view exact; the +2 % chain bar is missed by 0.04 points,
and the lanes are idle, which the chain policy allows. Derive the record bundle from packet190 with the `k3x-diet` selection
and packet194's engine; prepare a fresh eleven-window chain on cards 0+1; its WS128 must beat 62.345282
(cmvk51wfn001gng01fpbfy89q) and pass every exactness gate."
`bracket_gate.py` recomputes packet194's two lane-B rows from the raw tokens, clocks and proposals; the 126 files it reads are
pinned by sha256 where packet194 retained them (`evidence/bracket-gate.json`; READY carries the map's digest). The chain
rule (≥ +2 % and ≥ 63.592) is recomputed and recorded as **not met** (shortfall 0.038 points); the chain is admitted under
`policy195.json` `coordinator_idle_lane_exception_authorized: true` with the ruling quoted. Without that flag the gate refuses.

| View | Rate (tok/s) |
|---|---|
| k3x-diet (row 1, one load) | 63.474, 63.413 |
| k3x in-load (20-key control, production gate/up) | 62.168, 62.155, 62.193 |
| k3x-diet smoke (row 0, 12 × 64 + incident64) | 63.115 (data proof passed) |

- The slower k3x-diet view is +1.962 % over the fastest k3x view; k3x drift 0.061 %.
- Every view 13/13 exact (78 checks), identical proposals and acceptance, gate/up saving 10.8 (rank 0) / 11.8 (rank 1) µs per
  layer from the host scopes, no kill rule fired.

This admits a chain, not a record. The scope is 128 tokens; strict512 and `realistic_final_gate` stay false.

## Chain windows and expected durations

Lane **A**, cards **0+1** (PCI 0000:23:00.0 / renderD130 and 0000:27:00.0 / renderD131). Output
`stage2/packet195-record-bundle-diet/build/device-cards01-p195-a` (git-ignored `build/`), which must not exist yet.
Windows, argv and gaps (90 s) are packet136/187/190's. Expected durations are packet187's chain of 2026-10-22 (packet190's
chain of 22:06–22:53 UTC the same day took 47 minutes in all); the diet shortens decode by ~2 %, so the suite windows may be a
few seconds shorter.

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
   (25 GB + the chain's planned 3,324,718,708 B). At preparation time root free was 30.9 GB (margin ~2.5 GB).
3. **Dry run:** `bash experiments/own-xpu-runtime/ops/packet195-orchestration/launch_chain.sh --dry-run`
   (every check incl. `verify_ready.py`; prints `dry run: every check passed; would run: systemd-run --user
   --unit=packet195-chain-a ...`).
4. **Launch:** `bash experiments/own-xpu-runtime/ops/packet195-orchestration/launch_chain.sh`. It repeats the
   checks, runs exactly `ready.json.chain_command` (below), waits at most 120 s for `packet195-chain-a` to become
   active and returns. It never retries.
5. **Watch:** `systemctl --user is-active packet195-chain-a`; `journalctl --user -u packet195-chain-a`;
   `<output>/queue-state.json` (`completed` grows window by window); `<output>/<W>/window.json`;
   `<output>/queue-all-complete.json` at the end; the launcher log `$FN/p195-launch.log`
   (default `/tmp/claude-1000/-home-steve/fn-run`).
6. **After the chain,** restoring PAUSE-A and the endpoints is the coordinator's decision. On a fault, follow the
   fault-halt rules. Nothing here resets, restarts or retries.

```bash
systemd-run --user --unit=packet195-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet195-orchestration/device-entry.sh chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/build/device-cards01-p195-a </dev/null
```

`device-entry.sh` reruns `verify_ready.py`, builds the closed library environment, enters `coordinator_windows.sh`
and `chain_entry.py queue`, which reruns `verify_cpu`/`verify_ready` before the windows. Each window keeps
packet136's lane admission, drain spacing, watchdogs and fault handling.

`launch_chain.sh` refuses (rc 4) when: an endpoint is active; PAUSE-B is absent or PAUSE-A present; an
`inflight-A/B.json` or `active-lane-A/B.json` marker exists; a `lanequeue-*`, `window-*` or `packet195-chain-a` unit
is active (the caller's own unit excluded); an earlier `packet195-chain-a` exists in any non-inactive state; memory
or disk is below the floor; the output exists; `verify_ready.py` fails or its command differs. It never creates or
deletes a PAUSE file and never starts or stops a service. `P195_LANE_DIR`, `P195_COORD_DIR`, `P195_MEMINFO` are
rehearsal-only overrides and force `--dry-run`. `proposal.jsonl` is an entry-check descriptor; never queue it.

## Submission (after a finished, exact chain)

```bash
# 1. Prepare the bundle. Read-only on the chain; never posts. Refuses unless WS128 is exact and > 62.345282.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet195-orchestration/prepare_submission.py \
  --chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/build/device-cards01-p195-a \
  --output experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/submission/prepared-a </dev/null
# 2. Local dry run: shared preflight plus the packet195 validator. No key, no network.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet195-orchestration/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/submission/prepared-a/payload-queue.json --dry-run </dev/null
# 3. Coordinator only: authenticated server dry run (LMX_API_KEY or the key file; never print it).
#    ...same command... --server-dry-run
# 4. Coordinator only: the real submit, with no flag. Receipts go to data/localmaxxing-responses/ with key lines filtered.
# 5. After an approved submission: append the record to scripts/packet49_record_threshold.json (improvement only).
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet195-orchestration/prepare_submission.py \
  --update-record experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/submission/prepared-a/result.json --submission-id <ID> </dev/null
```

(packet190 ran `prepare_submission.py` under `taskset -c 4-15,20-31`; the tool refuses the reserved cores 0-3/16-19.)

`evidence/submission-rehearsal.json` (CPU) covers the historical packet136 replay (refused by the current floor; a
tampered output refused), the k3x-diet notes and flags on an in-memory relabel (1,726 of 2,000 chars: `expert_gateup=diet`,
`p193diet::GateUp`, BIT-IDENTICAL, 0 B of allocation, k3x layers 24-26 / QSA layer 27, kernel_io/rank0_prepare/boundary_export,
62.345282, `cmvk51wfn001gng01fpbfy89q`, Packet194 screen, **128-token capped scope**, strict512 false; engine flag
`expertGateUp` with kernel, production kernel, sites per rank, bitIdentical and allocationDeltaBytes 0; `v3Boundary`,
`k3xTrims`), the local `--dry-run` path (a foreign payload blocked, rc 2, no key, no network) and the record-update path on
scratch ledgers (the real ledger unchanged; the 62.345282 floor refuses packet136's 58.798 replay). `--server-dry-run` was
**not** run: it needs the key (coordinator).

## CPU reproduction and gates

- CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`, at most 4 GiB; CPU work stops
  below 27 GB free. Poll `systemctl --user list-units 'window-*' 'lanequeue-*' 'packet*'` before any compile or heavy
  step (`compile_poll.py`; an endpoint-restore `window-*` unit, ExecStart argv ending in `-restore<N>`, is tolerated and
  recorded).
- **Reseal order after any edit:** `place_diet.py`, `select_diet.py`, `guard_layout195.py` (packet side) →
  `cpu_bytes.py` → `preparation_probe.py` → `seal195.py` → the affected gates (`argument_gate.py`,
  `run_preparation.py`, `transport_gate.py`, `entry195.py`, `launch_limit_gate.py`, `drain_check.py`,
  `bracket_gate.py`, `make_proposal.py`, **`seal195.py` again** (the orchestration snapshot pins `proposal.jsonl`),
  `chain_adapter.py check_inputs.py --report evidence/input-check.json`, `rehearse_entry195.py proposal.jsonl --report`,
  `prepare_submission.py --rehearse-packet136`, the three unit tests → `finalize195.py` → `final_checks.py --ready`,
  which writes READY **last** and reruns the pin guard and the launcher rehearsal; any failure withdraws READY.
- Gate receipts are in `evidence/`; `cpu-receipts.json` binds them; the packet README has the table.
- **Pin guard.** The live `ops/lane-queue/pin_guard.check_job` on `proposal.jsonl` finds 0 cross-packet mutable pins
  before and after READY (`evidence/final-checks.json`, `evidence/final-pin-guard.json`). Every ops file is pinned
  through its byte copy in `orchestration-snapshot/` and must equal that copy at launch.
- **Live-launch verification** (by `verify_cpu`/`verify_ready`, not by the guard): the ops code; the 126 packet194
  bracket files (`evidence/bracket-gate.json`); the four shared submission scripts (vendored in
  `lineage-inputs/dependencies/`).
- `evidence/packet136-chain-evidence.json.gz` (hard link of packet190/187's copy) is retained for the rehearsal.
  `real_report.py` replays packet190's record chain (`stage2/packet190-record-bundle-k3x/build/device-cards01-p190-a`,
  git-ignored, read in place; it must reproduce 62.345281904743764) because packet136's chain output was archived off the
  root disk on 2026-10-22. Parked helpers are in `lineage-p195-scaffolding/` and do not control admission.
