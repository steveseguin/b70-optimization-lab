# Packet 45 device qualification: rounds 1-5 (2026-10-13 to 2026-10-15)

Packet 45 (`experiments/own-xpu-runtime/stage2/packet45-merged3`) merges the measured-but-unused kernel wins
and moves the draft head to rank 0. It targets about 45 tok/s on two B70 cards for the IQ3 Flash-Next
own-runtime line. Its device chain is K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, followed by the WS128x/WS128
speed pair. Each window stops at its first failure, so each device round has found exactly one defect.
All rounds ran on boot `13858eef-ec68-44ea-a67c-9444933b7100`.

The chains are:

| Chain | Cards | Context | Draft rank |
|---|---|---:|---:|
| `947-p45a` | 0-1 | 4096 | 0 |
| `948-p45b` | 2-3 | 4096 | 1 |
| `949/955-p45c` | 0-1 | 32768 | 0 |
| `950-p45d` | 2-3 | 32768 | 1 |

No tok/s has been measured yet. The furthest point reached is the P39 gate, about ten minutes into K2.

## Rounds

All times are UTC.

| # | Launch | Failed at | Defect | Fix commit | Verified on device |
|---|---|---|---|---|---|
| 1 | 10-13 23:23 | K1a | HC/SiLU NaN payload differs host vs device (`actual adapter core mismatch case=54 version=0 buffer=5`) | `9b5a4ec70` | yes, round 2 (K1a 218 + 216 checks) |
| 2 | 10-14 05:25 | K1a gate | `sequential_teardown(row,4)` still expected packet 44's four owners; the merge adds a fifth, `p39-fixture-*`, all clean | `fd650dd1c` | yes, round 3 |
| 3 | 10-14 11:24 | K1b admission, before device contact | 2.5 GB K1b retention reserve + 1.55 GB seal-bound build tree > packet-38-era 3 GB build cap; the CPU rehearsal admitted a fake 64 MB | `7244b704d` | yes, round 4 (K1b passed) |
| 4 | 10-14 17:21 | K2, first line | fused route+gather (`p42.route.production_rank32`) adapter mismatch, all three versions, both ranks | `13cb290b0` | yes, round 5 (K2 ran 400 lines past it) |
| 5 | 10-14 23:24 | K2, P39 gate | P39's first expert-bank upload of 268,697,600 B exceeds CopyEngine's 134,217,728 B per-copy limit (`owner.cpp:310`, "copy extent/lifetime") | in progress (fix 5, `COPY-EXTENT-CLOSEOUT.md`) | pending |

Every failure was identical on both card pairs. The kernel log has no xe/GuC reset, hang or fault line after
2026-10-12; the last ones are the known 10-10/10-11 incidents. In every incident, the failing rank's teardown
record shows `failure-before-teardown`, exit code 75, `safe_to_exit=false` and `in_flight=0`.

Device evidence:
- Round 1 is in `build/incident-20261013-k1a-case54/`.
- Rounds 4 and 5 are in `build/incident-20261014-k2-routegather/` and `build/incident-20261014-k2-copyextent/`.
- Codex keeps tracked copies under `evidence/<fix>/` in the packet.
- `build/` is git-ignored, so `data/own-xpu-runtime-packet45-device-rounds-20261014/incident-file-index.tsv`
  records the SHA-256 and size of every incident file.
- Round 3's chain directories (K0/K1a pass, K1b refusal) were deleted at the round-4 relaunch. Rounds 4 and 5
  re-prove those windows.

Coordinator records are in `data/own-xpu-runtime-packet45-device-rounds-20261014/`. They had lived only in
`/tmp`, which a reboot wipes. The folder holds:
- the queue log;
- each chain's last log;
- the chain and WS128 scripts;
- runners v3 and v4;
- every Codex brief;
- the tail of each Codex log.

## The common cause of defects 3 and 5

Two of the five defects are host-side size checks that no CPU rehearsal can reach, because the rehearsals
shrink bytes:
- `window.py` admits 64,000,000 bytes under `cpu_rehearsal`;
- `fixture_validation::only` allocates zero-byte weights.

Fix 5 adds `copy_extent_gate.cpp`, which runs the real owner and CopyEngine at production sizes on a sparse
backend for all eight P39 classes. W0p, KD, W2m, WS, WSs and WS128x/WS128 have never run on this binary.
Audit 6 (`briefs/brief-p45audit6.md`) applies the same production-size check to all of them before the next
relaunch. That way, the remaining size defects are found in one CPU pass instead of one device round each.

## Coordinator process defects found in review (2026-10-15)

1. **Wrong crash site in round 5.** The coordinator blamed GEMV-logits winner adoption. The C++ timing loop
   adopts nothing; selection happens later in Python `k2_summary`. Logits is the last GEMV shape, and the
   silent small-GEMV gate and then P39 run after it. `K2/run0/p39-failure.json` named the gate directly.
   Codex found the right site anyway. Rule: list `run*/*-failure.json` before reading a site from the last
   stdout line.
2. **The latch was cleared before the runner was killed** (rounds 4 and 5). The runner's 90 s gap launched
   949/950 at 17:32:08 in round 4. Only the boot fault latch refused them (`window.py:375`), with no device
   contact. Runner v4 now writes `queue/STOP` and exits on any failure, so no kill is needed and the latch can
   be cleared after it has exited.
3. **The runner never read p45 main-item logs.** It looked for `S/p45a-chain.log`, while the p45 scripts write
   `S/947-p45a-chain.log`. Every p45 main item was therefore recorded as FAIL with an empty tail. A passing
   chain would have marked its group failed and skipped its WS128 speed pair. The p44 scripts used unnumbered
   names, which is why p44 worked. v4 reads both names. It was dry-tested on a throwaway queue: ok + ok, then
   main fail halts; ok + companion fail halts.
4. **Stale `.skip` markers.** `951/952-p45a-WS128*.sh.skip` from round 4 were never cleared. The relaunch
   reset must clear the p45 `.fail`, `.skip`, `.done`, `GROUPFAIL-p45*` and `companion-*p45*` markers.
5. **Queue order.** The 32768 chains ran before the WS128 speed pairs, although the WS128 pairs depend only on
   the 4096 receipts. `949-p45c-chain` was renamed `955-p45c-chain`, together with its LOG path, so the first
   tok/s arrives hours earlier.
6. **Claims to drop.** "p33.dense.segment beat the incumbent (1418 vs 1926 us)" is not new evidence for 45 tok/s.
   p33 is one of the merged, previously measured wins, and this was an isolated fixture timing worth about
   0.5 ms per token (about 2%) at most. Also, `pgrep -af "codex exec" | wc -l` counted unrelated processes;
   the log mtime is the liveness signal.

## Relaunch procedure (after fix 5, and audit 6 if it reseals)

1. Confirm that the runner is not running and that `queue/STOP` holds the halt reason.
2. Read the failing rank's teardown record (`in_flight`, `live_bytes`) and the kernel log for the run window,
   using local time or `@epoch`.
3. Move `build/FAULT.json` and the `c*-gpu` directories into a new `build/incident-*` directory.
4. Clear the p45 queue markers and `STOP`.
5. Start `queue-runner4.py`.
