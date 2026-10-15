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
| 5 | 10-14 23:24 | K2, P39 gate | P39's first expert-bank upload of 268,697,600 B exceeds CopyEngine's 134,217,728 B per-copy limit (`owner.cpp:310`, "copy extent/lifetime") | `4bd493a72`, sealed `8a84cf7a0` | yes, round 6 (K2 passed) |
| 6 | 10-15 01:24 | KD host reference, before device contact | K2 enabled `small.gdn.ab=round2` and `small.ffn=p30.small.rows4` on both pairs; the KD plan has a sibling group that fails `main.cpp:656` ("small GEMV sibling schedule/input") instead of running unfused | `564b356a1`, sealed `f912fdaf6` | yes, round 7 (KD passed both pairs) |
| 7 | 10-15 02:03 | W2m admission, before device contact | `pipeline.py:442` requires `OMP_NUM_THREADS=2` in the window process, but the sealed `coordinator_windows.sh` launches with `env -i PATH LD_LIBRARY_PATH` only. WINDOW.md says the wrapper supplies it, and packet 44 did. The identity records the present env keys, so a resume from W2m is impossible; the chain restarts from K0 | coordinator launcher copy `runner/coordinator_windows_omp2.sh` (sealed script + `OMP_NUM_THREADS=2` in both `env -i` lists); WS128 queue scripts patched the same way; no code change or reseal | yes: full chain K0-WSs passed both pairs 02:43 |

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

Coordinator records are in `data/own-xpu-runtime-packet45-device-rounds-20261014/` (logs stored as `.txt`, since `data/**/*.log` is ignored). They had lived only in
`/tmp`, which a reboot wipes. The folder holds:
- the queue log;
- each chain's last log;
- the chain and WS128 scripts;
- runners v3 and v4;
- every Codex brief;
- the tail of each Codex log.

## Result (2026-10-15): exact on every gate, but slower than the record, so not submitted

The sealed `f912fdaf6` chains passed K0-WSs on both pairs. W2m matched 64/64 tokens and 384/384 layers; WS and WSs matched 12/12 prompts. WS128x and WS128 were qualifying (12/12 × 128 tokens). Same-boot packet-44 controls were rerun from the record's own per-window commands into `packet44-context/build/c4096ctl15{a,b}`.

Columns: class-balanced is the record metric; r0 and r1 are busy per interval for rank 0 and rank 1; fwd0 and fwd1 are the per-position forward times (prepare + enqueue + wait, positions ≥100).

| Run | Cards | Decode tok/s | Class-balanced | r0 | r1 | fwd0 | fwd1 | Hit | Miss | Acceptance |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| p44 record (10-13) | 0-1 | 37.589 | **37.856** | 23.49 | 22.59 | 19.17 | 18.84 | 23.19 | 39.33 | 0.791 |
| p44 control (10-15) | 0-1 | 37.732 | | 23.40 | 22.59 | 19.14 | 18.85 | 23.20 | 39.22 | 0.791 |
| p44 control (10-15) | 2-3 | 37.573 | | 23.48 | 22.71 | 19.13 | 18.94 | 23.25 | 39.42 | 0.791 |
| p45 draft rank 0 | 0-1 | 34.059 | 33.835 | 27.42 | 21.76 | 17.42 | 22.55 | 25.41 | 46.92 | 0.791 |
| p45 draft rank 1 | 2-3 | 30.956 | 31.025 | 28.54 | 21.48 | 20.94 | 18.33 | 28.22 | 49.00 | 0.791 |

The control reproduces the record on both card pairs, so there is no drift and no card-pair effect, and the packet-45 regression is real. Acceptance is identical, so outputs and guesses are unchanged. The pure regression is time spent outside the forward pass on rank 0 (busy minus forward: about 4 ms in p44, 7.5-10 ms in p45) together with miss cycles about 8-10 ms longer. In packet 45, draft rank 1 is worse than draft rank 0. The 32768 chains were skipped (`955-p45c-chain.sh.skip`) because they cannot help a slower build. Attribution: `experiments/own-xpu-runtime/stage2/packet45-merged3/REGRESSION-ANALYSIS.md` (Codex, in progress).

## Round 5 to 6 turnaround (2026-10-15)

On the owner's directive (no long CPU runs), the coordinator stopped the fix-5 reseal at 01:05 UTC. Codex
then did three things:
- committed fix 5 (`4bd493a72`);
- added a never-qualifying `--diagnostic-unsealed` window mode (`c726c601d`), which publication and submission
  helpers refuse;
- resealed by rebinding the existing real-model evidence (`8a84cf7a0`), with no real-model, compiler-matrix or
  sanitizer rerun.

Fix 5 reached the sealed device chains 19 minutes after the directive. Before that, each fix round had cost
3-6 h. Round 6's KD defect depends on which kernels the device chose: it exists only after K2's measured
dispatch enables the small-GEMV fusions. It reproduces exactly on CPU from the saved
`K2/run0/dispatch-measured.json`. Evidence: `build/incident-20261015-kd-smallgemv/`.
Fix 6 went from the KD failure to a relaunch in 29 minutes. Seal 6 (`f912fdaf6`) records a named amendment: for fix 6's
`main.cpp` change, the device suite windows (every emitted token compared with the oracle) replace the pre-device
real-model CPU suite. Any publication must cite those windows. Round 7's W2m evidence:
`build/incident-20261015-w2m-omp-env/`.

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

7. **Queue reset under a live runner (2026-10-15 04:12).** `queue-runner4.py` idles and polls for up to 6 hours after its last item. The coordinator cleared the packet-45 `.done` markers to prepare the speed-repair-1 relaunch while the control runner was still alive. It launched 947/948 at 04:12:22, before the coordinator had verified the seal. The run was valid only because Codex had written the speed-repair-1 `build-receipt.json` (`a199dffa…`) at 04:11:48, and every window re-checks the sealed sources and artifact hashes. Rule: write `queue/STOP` (or confirm no runner is alive) before touching queue markers. Reset markers only at the moment of launch.

## Relaunch procedure (after fix 5, and audit 6 if it reseals)

1. Confirm that the runner is not running and that `queue/STOP` holds the halt reason.
2. Read the failing rank's teardown record (`in_flight`, `live_bytes`) and the kernel log for the run window,
   using local time or `@epoch`.
3. Move `build/FAULT.json` and the `c*-gpu` directories into a new `build/incident-*` directory.
4. Clear the p45 queue markers and `STOP`.
5. Start `queue-runner4.py`.
