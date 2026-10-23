# Packet183 win-path waiter: arming (device-window driver only)

Preparation did NOT arm, queue or launch anything. The waiter is `chain/p183_win.py`
(entry `chain/p183-win.sh`). The device-window driver arms it in an approved two-card window,
before the lane-B rows start, as its own systemd user unit (a session background job dies with
the session; see `notes/2026-10-21-own-runtime-window-pin-guard-refusal.md`).

## What "win path" means for two cards

There is no derivable two-card record chain today: a two-card record chain is a record bundle
(packet136 + `dense_scales=metadata`, its own build and a fresh registered chain on cards 0+1, the
way packets 136 and 143 did it). That bundle is the next packet and is built only after this
bracket wins. The win action that exists and is entry-rehearsed is the **lane-A confirmation
bracket of this packet on cards 0+1** (packet136's two-card promotion policy required wins on
both lanes; the record chain will run on cards 0+1).

## Order inside the window

1. Run the live plan on a private copy first:
   `python3 -B experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane B --directory <tmp>`
   with `<tmp>/queue-B.txt` = `ops/lane-queue/proposed-p183-two-card-B.txt` (both rows) and the
   queue's `*.py` copied into `<tmp>`. Only if it says `passed` for both rows: stop the owner's
   endpoints by the usual window procedure. All three must be stopped: lane B uses cards 2+3
   (`qwen38-27b-vision` holds cards 1+2, `qwen38-27b-fp8-tp1-test` card 3) and the whole-host
   memory bound needs the rest (`qwen38-27b-fp8` card 0). MemAvailable must reach
   105,411,248,128 B + 1 GiB at START (the 2026-10-22 windows measured 120.6-120.7 GB with the
   endpoints stopped).
2. Keep `PAUSE-A` in place for the whole window (two-card resident rows are whole-host).
   Archive/remove `PAUSE-B` for the window as usual.
3. Arm the waiter (exact command, from the repository root):

   ```bash
   systemd-run --user --unit=p183-win --property=Restart=no \
     --working-directory=/home/steve/llm-optimizations \
     /usr/bin/bash experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/chain/p183-win.sh
   ```

   Proof it is armed: `systemctl --user is-active p183-win` is `active` and
   `/tmp/claude-1000/-home-steve/fn-run/p183-win.log` ends with
   `p183-win armed: waiting for packet183-s1-bracket-B`.
4. Queue both proposal rows (smoke then bracket, in file order) into `queue-B.txt` and start the
   lane runner as a `lanequeue-B<N>` unit. The window is running only once `events-B.jsonl` shows
   `START packet183-s1-smoke-B`.
5. **Do not end the window when the bracket row is DONE.** After the bracket's terminal event the
   driver waits until `systemctl --user is-active p183-win` is no longer `active`/`activating`
   (deadline 2.5 h) and only then writes STOP-B, re-arms PAUSE-B and restores the endpoints.
   Fail-safe if it does not: the waiter refuses to launch while any of `qwen38-27b-fp8`,
   `qwen38-27b-fp8-tp1-test`, `qwen38-27b-vision` is active (exit 5, logged) and checks again
   right before the launch.

## What the waiter does after the bracket

- Bracket not DONE (including SKIPPED-DEPENDENCY after a failed smoke), no summary, or a summary
  the decision rule refuses: exit 2, nothing else.
- Chain rule not met (`v5/s1_decision.py`: drift <= 3%, both metadata views >= +2% over every
  control and >= 1.02 x 58.798109 = 59.974 tok/s; exactness and identical draft proposals are
  enforced upstream): logs the decision, exit 0 (normal end; the bracket summary is the readout).
- Chain rule met: endpoints inactive, confirm output fresh, live `lanequeue.py` byte-equal to the
  packet's planning snapshot; the lane-A job (proposal bracket row, lane A, unit
  `screen-packet183-s1-confirm-A`, output `v5/evidence/device-metadata-v5-A-p183`) is validated,
  pin-guarded and `--plan`ned through the queue's own functions; then PAUSE-A/B are held (contents
  saved, hold text written; never deleted), the waiter waits for inflight/active markers (30 min),
  drain spacing (61 s), the queue guards (kernel fault count == reviewed base 2, markers, latches),
  host memory and storage admission and the endpoints again, runs a fresh fault review, and runs
  exactly `lanequeue.command(job, review, receipt, ldp)` (systemd-run --wait). No retry. A 2 h
  client deadline never signals the unit. PAUSE files get their saved contents back (a pause that
  did not exist keeps the hold text). Both lanes' decisions go to `v5/evidence/waiter-decision.json`.

Exit codes: 0 done / no confirmation needed, 2 bracket not DONE or refused, 3 deadline, 4 derived
input refused (proposal, existing output, queue drift), 5 endpoint active, 6 markers busy 30 min,
7 host memory or storage admission, 8 confirmation without a passed summary, 9 client deadline.

## After the window (coordinator)

- Commit `v5/evidence/device-metadata-{smoke,v5}-B-p183/*.json` (and `-A-p183` if the confirmation
  ran) and the logs at once; bulky `run/` trees stay ignored, not deleted.
- On a lane-B (and lane-A) chain-rule win: prepare the record bundle (packet136 + `dense_scales`
  metadata, S1 TU + dispatch, fresh chain on cards 0+1) as its own packet; nothing in this packet
  certifies a record.
- On a loss: append the DO-NOT-REPEAT row from the summary (`s1_decision`), close S1, and per
  packet177 also close S2 unless the metadata views reached B/A <= 0.90.
- Re-arm PAUSE-B with the owner text and restore the endpoints as in the 2026-10-22 windows.

Durations: smoke ~3 min (packet153 smoke 01:40-01:43 UTC; plan 240-360 s), bracket ~8.5 min
(packet153 01:45:24-01:53:38 UTC; plan 480-900 s), 61 s queue spacing between rows. Waiter checks
~3 s. Confirmation bracket ~8.5 min. Whole window on a win ~25 min plus endpoint stop/restore;
on a loss ~13 min plus endpoint stop/restore.
