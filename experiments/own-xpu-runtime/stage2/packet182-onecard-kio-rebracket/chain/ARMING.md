# Packet182 win-path chain waiter: arming (device-window driver only)

Preparation did NOT arm, queue or launch anything. The waiter is `chain/p182-win.sh`.
It is armed by the device-window driver in an approved lane-A window, before the v5 row
starts, as its own systemd user unit (a session background job dies with the session; see
`notes/2026-10-21-own-runtime-window-pin-guard-refusal.md`).

## Order inside the window

1. Run the live plan on a private copy first:
   `python3 -B experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane A --directory <tmp>`
   with `<tmp>/queue-A.txt` = the JSON line of `ops/lane-queue/proposed-p182-one-card-A.txt`.
   Only if it says `passed`: stop the endpoints by the usual window procedure (MemAvailable
   must reach 98,990,252,032 B + 1 GiB at START; the 2026-10-22 windows measured 120.6-120.7 GB).
2. Keep `PAUSE-B` in place for the whole window (v5 and chain). Archive/remove `PAUSE-A` for
   the window as usual.
3. Arm the waiter (exact command, from the repository root):

   ```bash
   systemd-run --user --unit=p182-win --property=Restart=no \
     --working-directory=/home/steve/llm-optimizations \
     /usr/bin/bash experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket/chain/p182-win.sh
   ```

   Proof it is armed: `systemctl --user is-active p182-win` is `active` and
   `/tmp/claude-1000/-home-steve/fn-run/p182-win.log` ends with
   `p182-win armed: waiting for packet182-one-card-v5-A`.
4. Queue the v5 row (the proposal's JSON line into `queue-A.txt`) and start the lane runner as
   a `lanequeue-A<N>` unit. The window is running only once `events-A.jsonl` shows
   `START packet182-one-card-v5-A`.
5. Do not hold `fn-run/onecard-hold.lock` past the v5's DONE: the waiter takes it before the
   chain (it waits up to 2 h for it).
6. **Do not end the window when the queue row is DONE.** The 2026-10-22 driver
   (`window-2026102x-*.py`: watch -> STOP-A + re-arm PAUSE-A -> restore endpoints) would restore
   `qwen38-27b-fp8` onto card 0 while the chain needs card 0 and the whole host. For packet182 the
   driver must, after the v5 row's terminal event, wait until `systemctl --user is-active p182-win`
   is no longer `active`/`activating` (deadline 2.5 h: 3 h waiter deadline minus the v5) and only
   then write STOP-A, re-arm PAUSE-A and restore the endpoints. Fail-safe if it does not: the waiter
   refuses to derive or launch while any of `qwen38-27b-fp8`, `qwen38-27b-fp8-tp1-test`,
   `qwen38-27b-vision` is active (exit 5, logged), and `p182-chain.sh` re-checks right before launch.

## What the waiter does after the v5

- Not DONE, no summary, or the chain rule fails (`chain/chain_gate.py`: 60/60 exact, drift
  <= 3%, minimum gain >= +2%, slower B view >= 1.02 x the live record 34.573038): logs and
  exits; no chain. NOCHAIN is a normal end.
- Rule met: derives `stage2/packet182c-chain` + `ops/packet182c-orchestration` with
  `chain/derive_chain.py` (ops generator unchanged on disk; flag block before the entry guard;
  post-native rehearsal carried from packet176c when no real chain evidence exists), then
  refuses unless `chain/script_argv_check.py`, `--predevice-check` and `--closure-check` pass;
  runs and logs `--postnative-check`; `p182-chain.sh --check`; takes the one-card lock, sets
  `fn-run/QUIET`, and runs `chain/p182-chain.sh` (unit `packet58-onecard-182-a`, 7 windows,
  ~35 min). PAUSE-A/B are held during the chain and their earlier contents restored after; the
  script never deletes a PAUSE file.

## After the window (coordinator)

- Commit `screen/evidence/card0-182-v5-a/resident/*/{summary,window,queue}.json` and logs at once
  (the bulky `run/` trees are ignored, not deleted). If a chain ran, commit
  `stage2/packet182c-chain` and `ops/packet182c-orchestration` with the chain summaries.
- Submit only if the chain's fresh WS128 is exact and above the live ledger threshold
  (`scripts/packet58_onecard_record_threshold.json`); the derived packet's submission policy
  enforces it.
- Re-arm PAUSE-A with the owner text and restore the endpoints as in the 2026-10-22 windows.

Durations: v5 ~13-14 min (packet176 v5 unit 13 min 20 s; plan range 700-1200 s, watchdog
7200 s). Waiter derive + checks ~20-40 s (CPU rehearsal: derive 5.5 s). Chain ~35 min
(chain 176-a 12:01:09-12:36:11 UTC). Whole window on a win ~55 min plus endpoint stop/restore.
