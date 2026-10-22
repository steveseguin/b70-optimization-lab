# Packet187: V3 two-card record chain (orchestration)

Packet187 is bundle 8 (packet136's record selection) plus two changes:

- packet153's static snapshot (`snapshot_host=static`, `probe=off`, `dense_scales=expanded`);
- packet186's V3 verified-boundary rebalance (`rank0_layers=0-25`, `boundary=rank0`).
  Rank 1 keeps the full target head. Rank 0 runs GDN layers 24-25 for the verified
  token, and rank 1 starts at layer 26.

The arithmetic is `iq3-p49-split32-v1` with BF16 KV, draft prefix 80,128 and a rank-1 MTP draft.

The packet uses the same selection, plan and engine as packet186's V3 arm:

- selection sha256: `923639a9c03fe8b5...`;
- memory plan and dispatch: byte copies of packet186's v3 files;
- device engine: `693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739`;
- gnu-host engine: `9035149a8cce1f98...`.

Both engines are reused byte for byte from packet186 `v5/build`. There was no compile and no relink.
`inputs/packet186-native.json` binds both engines and the native sources. It has a packet copy in
`stage2/.../lineage-inputs/`.

**Admission.** The coordinator ruled on 2026-10-22 that the chain rule is met.
`bracket_gate.py` recomputes packet186's four lane-B rows from the raw tokens, clocks and proposals.
The 169 files it reads are pinned by sha256 where packet186 retained them, in `evidence/bracket-gate.json`.

| View | Rate (tok/s) |
|---|---|
| V3 | 60.573, 60.533 |
| Split-head controls | 58.595, 58.441 |
| U | 57.832, 57.802, 57.840 |

- The slower V3 view is +3.306% over the faster split control and at least 59.974 tok/s.
- All 104 checks are exact, with identical proposals and acceptance.

This admits a chain, not a record. To be submittable, the fresh chain's WS128 must:

- exceed **58.798109**, the current record `cmve4dtir007wrf01k57sdf23`;
- pass every exactness gate.

The scope is 128 tokens. strict512 and `realistic_final_gate` stay false.

**The fix to packet155's chain failure.** Packet155-chain-a stopped in W0p with `shared extent`. The
cause was the chain transport file size (`3*SLOT+4096`) against the v5 engine's
`4*SLOT+4096+64` = 266,304 B. `chain_pipeline.py` and `pipeline.py` now use the engine's size.
`transport_gate.py` runs the real W0p canary through the chain code with the V3 gnu-host engine:

- 1000 handovers pass;
- the old size reproduces `shared extent` in both ranks;
- the miniature decode gives V3 = bundle 8 (24 tokens, 96 fixtures, identical proposals).

**KD.** The layer-streaming draft-capture reference projects the target-only keys:

- `rank0_layers=0-23`;
- `boundary=none`;
- `snapshot_host=production`.

V3's resident split cannot stream.

## Chain windows and expected durations

Lane **A** uses cards **0+1**: PCI 0000:23:00.0 (renderD130) and 0000:27:00.0 (renderD131). The output
is `stage2/packet187-record-bundle-v3/build/device-cards01-p187-a`, which must not exist yet. The windows
and argv are packet136's, with a 90 s gap between windows.

The expected durations come from packet136's record chain on 2026-10-18 (16:55:53-17:42:05Z). Each value
is the time from the previous window's end plus the gap to the end of this window. Packet155's K0-K2 on
the v5 engine matched these to within 2 s. Packet143 has no chain output on disk.

| Window | Purpose | Expected | Watchdog |
|---|---|---:|---:|
| K0 | JIT smoke, one process per card | 67 s | 600 s |
| K1a | kernel fixture checks (packet45 dispatch), first program | 89 s | 10,800 s |
| K1b | kernel fixture checks, second program | 87 s | 10,800 s |
| K2 | kernel class timing, which writes the measured dispatch used later | 366 s | 14,400 s |
| W0p | pipeline concurrency canary (packet155's failure point) | 39 s | 600 s |
| KD | layer-streaming draft-capture reference | 166 s | 10,800 s |
| W2m | incident-retrospective, 64 tokens, two ranks, oracle-exact | 154 s | 10,800 s |
| WS | 12-prompt suite, 128 tokens, retains steps 1-8 | 223 s | 30,000 s |
| WSs | 12-prompt suite, 128 tokens, speed pair | 204 s | 30,000 s |
| WS128x | 128-token suite, retains steps 1-8 and 97-104 (exactness for WS128) | 237 s | 60,000 s |
| WS128 | **record window**: 128 tokens, no retention, class-balanced tok/s | 240 s | 60,000 s |

The windows take 1,872 s and the 10 gaps take 900 s, so the total is **about 46-47 minutes**.
V3 decodes slightly faster, so the suite windows may be a few seconds shorter.

## Launch procedure (coordinator only, by hand)

Nothing has been queued, armed or launched.

1. **Bring the host to the admission state.** Each of these is a coordinator decision:
   - Stop the three owner endpoints: `qwen38-27b-fp8` (card 0), `qwen38-27b-fp8-tp1-test` (card 3) and
     `qwen38-27b-vision` (cards 1+2).
   - Archive `ops/lane-queue/PAUSE-A` for the chain by moving it out of the lane dir. The launcher only
     requires that it is absent.
   - **Keep `PAUSE-B`.**
   - Make sure there is no lane job in flight and no other `window-*` or `lanequeue-*` unit is active.
   - For timing hygiene, freeze or stop `codex-*` units. This follows packet182's quiet-chain practice.
2. **Check the floors.**
   - `MemAvailable` ≥ 108,741,559,780 B. That is packet186 V3's 107,667,817,956 B plus 1 GiB.
   - Root free ≥ 28,324,718,708 B. That is 25 GB plus the chain's planned 3,324,718,708 B.
3. **Run the dry run:**
   `bash experiments/own-xpu-runtime/ops/packet187-orchestration/launch_chain.sh --dry-run`.
   It runs every check, including `verify_ready.py`. A pass prints `dry run: every check passed;
   would run: systemd-run --user --unit=packet187-chain-a ...`.
4. **Launch:** `bash experiments/own-xpu-runtime/ops/packet187-orchestration/launch_chain.sh`.
   It repeats the checks and runs exactly `ready.json.chain_command`, which is below. It then waits at
   most 120 s for `packet187-chain-a` to become active and returns. It never retries.
5. **Watch the chain.** No helper waits for the end.
   - `systemctl --user is-active packet187-chain-a`
   - `journalctl --user -u packet187-chain-a`
   - `<output>/queue-state.json`, whose `completed` list grows window by window
   - `<output>/<W>/window.json`
   - `<output>/queue-all-complete.json` at the end
   - the launcher log in `$FN/p187-launch.log` (default `/tmp/claude-1000/-home-steve/fn-run`)
6. **After the chain ends,** restoring PAUSE-A and the endpoints is the coordinator's decision. On a
   fault, follow the fault-halt rules. Nothing here resets, restarts or retries.

```bash
systemd-run --user --unit=packet187-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet187-orchestration/device-entry.sh chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/build/device-cards01-p187-a </dev/null
```

The launch path runs `device-entry.sh`, which:

1. reruns `verify_ready.py`;
2. builds the closed library environment;
3. enters `coordinator_windows.sh` and then `chain_entry.py queue`;
4. reruns `verify_cpu` and `verify_ready` before the windows.

Each window keeps packet136's lane admission, drain spacing, watchdogs and fault handling.

`launch_chain.sh` refuses (rc 4) when any of these is true:

- an endpoint is active;
- PAUSE-B is absent, or PAUSE-A is present;
- an `inflight-A/B.json` or `active-lane-A/B.json` marker exists;
- a `lanequeue-*`, `window-*` or `packet187-chain-a` unit is active (the caller's own unit is excluded);
- an earlier `packet187-chain-a` exists in any non-inactive state (inspect it by hand);
- memory or disk is below the floor;
- the output already exists;
- `verify_ready.py` fails or its command differs.

It never creates or deletes a PAUSE file and never starts or stops a service.
`P187_LANE_DIR`, `P187_COORD_DIR` and `P187_MEMINFO` are rehearsal-only overrides and force `--dry-run`.
`proposal.jsonl` is an entry-check descriptor. Never append it to a queue.

## Submission (after a finished, exact chain)

```bash
# 1. Prepare the bundle. Read-only on the chain; never posts. Refuses unless WS128 is exact and > the ledger threshold.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet187-orchestration/prepare_submission.py \
  --chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/build/device-cards01-p187-a \
  --output experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/submission/prepared-a </dev/null
# 2. Local dry run: shared preflight plus the packet187 validator. No key, no network.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet187-orchestration/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/submission/prepared-a/payload-queue.json --dry-run </dev/null
# 3. Coordinator only: authenticated server dry run. Uses LMX_API_KEY or the key file; never print it.
...same command... --server-dry-run
# 4. Coordinator only: the real submit, with no flag.
# 5. After a real submission: append the record to scripts/packet49_record_threshold.json. Only an improvement is accepted.
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet187-orchestration/prepare_submission.py \
  --update-record experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3/submission/prepared-a/result.json --submission-id <ID> </dev/null
```

`evidence/submission-rehearsal.json` (CPU) covers:

- **Historical replay.** Packet136's real evidence is replayed unchanged under its historical identity
  through `submission_evidence.py`. The current floor refuses it, and a tampered output is refused.
- **V3 notes and flags.** The payload is checked on an in-memory relabel: 1,171 of 2,000 chars,
  disclosing V3, `snapshot_host=static`, layers 24-25, rank 1 from 26, packet186, 128-token scope and
  strict512 false. All API string limits and identity flags are present.
- **The local `--dry-run` path.** It runs through `submission.py` with no key in the environment.
  Packet136's real payload is blocked: its runtime/seal pair is not packet187's pinned pair. rc is 2,
  and there is no key read and no network use.
- **The record-update path.** It runs on scratch copies. The real-ledger copy refuses a non-improving
  result and stays byte-identical. A truncated scratch ledger accepts the same real result as exactly
  one appended, validated row. The real ledger is unchanged.

`--server-dry-run` was **not** run because it needs the key. The coordinator runs it.

## CPU reproduction and gates

- **CPU commands** use `nice -n 19 taskset -c 8-15,24-31 python3 -B` with stdin `/dev/null` and at
  most 4 GiB. CPU work stops below 27 GB free.
- **Reseal order after any edit:**
  1. `place_v3.py`, `select_v3.py` and `guard_layout187.py` (packet side);
  2. `seal187.py`;
  3. the affected gates;
  4. `finalize187.py`;
  5. `final_checks.py --ready`, which writes READY **last** and re-runs the pin guard and the launcher
     rehearsal. Any failure withdraws READY.
- **Gate receipts** are in `evidence/`; `cpu-receipts.json` binds them. The packet README has the table.
- **Pin guard.** The live `ops/lane-queue/pin_guard.check_job` on `proposal.jsonl` finds 0 cross-packet
  mutable pins, before and after READY (`evidence/final-checks.json`, `evidence/final-pin-guard.json`).
  `guard_layout187.py` moved the inherited provenance under `lineage-inputs/`, following packet143's
  layout. `chain_seal.py` pins only packet bytes. Every ops file is pinned through its byte copy in
  `orchestration-snapshot/` and must equal that copy.
- **Live-launch verification.** These files are verified at launch by `verify_cpu`/`verify_ready`, not
  by the guard:
  - the ops code;
  - the 169 packet186 bracket files (`evidence/bracket-gate.json`; READY carries only their digest);
  - the four shared submission scripts. They were dropped from `dependency-pins.json` because the chain
    never imports them; their pinned bytes are vendored in `lineage-inputs/dependencies/`.
- **Retained evidence.** `evidence/packet136-chain-evidence.json.gz` (5.6 MB) is retained for the
  rehearsal. Parked helpers are in `lineage-p187-scaffolding/` and do not control admission.
