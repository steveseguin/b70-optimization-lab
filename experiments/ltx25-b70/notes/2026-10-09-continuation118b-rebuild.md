# LTX continuation 118b: CPU rebuild after the independent BLOCK review

2026-10-09. **Built and sealed, never launched, not XPU-qualified.**
Packet 118 is withdrawn and was never launched. Its sealed files and all existing run
directories were left unchanged. This task did no device work, model serving, launch
rehearsal, process signalling, systemd operation, port-8188 access or host-setting change.
Another agent's host work was neither inspected nor operated.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118b`.
Manifest: `248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1`.
Parent: sealed 117, `5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9`.
Superseded 118: `cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6`
(still unchanged). The parent is deliberately 117; withdrawn 118 is provenance, not a
runtime dependency. Recursive closure follows 117 → 116b → 116 → … → 111.

[Build receipt](../data/resume-20261008/continuation118b-build.json),
[launch reference](../recovery/20261009-continuation118b-stream/LAUNCH.md),
[client contract](../recovery/20261009-continuation118b-stream/CONTRACT.md),
[independent review](2026-10-09-continuation118-review.md).

## What changed and how each finding was closed

The retained [review-fixes.patch](../recovery/20261009-continuation118-stream/review-fixes.patch)
was applied to the 118 author sources. The extra timing fixes were made there too,
then copied into a separately identified 118b author tree. The sealed 118 tree was not edited.

1. **Wrong chunk's decode policy:** P7 always compares walk and fingerprint on the
   decode thread. It no longer depends on the prompt thread's mutable chunk counter.
   Xpu3Snapshot sends the actual P5 memory reading to the inspector; P7 makes no
   replacement memory read to decide policy. Near-floor comparison includes equality
   at 0.5 GiB. Either four-card dual sample can set the sticky near-floor flag.
2. **Missing memory verdict comparison:** dual snapshots compare memory admission
   (free floors, complete counter rows, nonnegative integer values, reserved/peak at
   least allocated), using before floors or the site's 2 GiB after floors. They do
   not compare sequential raw byte readings for equality. A verdict disagreement
   writes the snapshot latch and raises before admission. CandidateSafety is unchanged.
3. **Inherited cap and unknown launch mode:** both launcher env commands explicitly
   unset LTX_DECODER_GRAPH_POOL_CAP_GB before assignments. CAP=- is therefore uncapped.
   The tenth argument accepts only launch or --check-only; a typo rejects before
   operational commands. Verification here executed isolated argument/env fragments,
   never the launcher, a unit or its --check-only path.
4. **Timing race and overstated semantics:** keep the shared middleware marks and
   refresh them at receipt staging, so queued populated after executor entry can be
   recorded. If still unavailable it stays missing; no wait is introduced. queued
   means POST-handler return, not the exact queue insertion. first_served is stamped
   only after a successful read and HTTP 200 response construction. It does not mean
   completed delivery or fsync. Removed the extra route stat. Negative queue/commit
   intervals and missing values remain visible. Split closure proves accounting,
   not causal accuracy. CPU locks, allocations, timestamps and I/O add unmeasured cost.

The new identity follows the 116 → 116b precedent: string packet id `"118b"`,
`stream118b-` names, comparison mode `stream-candidate-118b-v1`, clip bases
11820000/11821000, unit `ltx118b-stream-server-20261009`, and `launch-118b.sh`.
Wire schemas and node classes remain 118. Numerical contracts and qualification ids
remain 118's; the new plan binds renamed graphs. Latches deliberately retain their
old names: decoder-graph-116, anchor-decode-117/118, precompute-117/118 and snapshot-118.
A rebuild cannot clear an existing safety refusal.

No tensor arithmetic or model operations changed. Comparing sealed 118 and 118b found
**2,378 identical request graphs after only namespace/clip-index normalization**, and
**132 identical numerical contracts and qualification ids**. The two packets have
1,873 identical regular files, 28 changed files, zero additions and zero deletions.
The builder independently preserves 117's sampler, decoder source, conditioning,
CandidateSafety, native bindings and other numerical source bytes. Receipts and
metadata do change; output video/audio byte identity remains a launch-time gate.

## Build and CPU validation

All Python commands used `/home/steve/.venvs/ltx25-baseline/bin/python3 -B`.
The builder inspected assembly first, then built exclusively into the new directory:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python3 -B experiments/ltx25-b70/recovery/20261009-continuation118b-stream/runtime_packet.py --build --input-inventory-sha256 9fb042c3e2bf5a4d0fb910b317a7db5d7362b5b70c41d0178da40ce2bf625f9a
/home/steve/.venvs/ltx25-baseline/bin/python3 -B experiments/ltx25-b70/recovery/20261009-continuation118b-stream/runtime_packet.py --verify-manifest-sha256 248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1
```

Both build-time and separate recursive verification passed. The manifest binds 1,899
files; total regular-file payload including manifest/status is 121,147,755 bytes.
Zero __pycache__ directories were found. Author input hashes match the sealed inventory.
No weights, runtime packet or large raw run artifacts are committed to Git.

| CPU suite | passed / total |
|---|---|
| Complete recovery test_*.py discovery | 299 / 299 (no skips) |
| Client 112 | 46 / 46 |
| Client 113 | 11 / 11 |
| Client 114 | 26 / 26 |
| Client 115 | 20 / 20 |
| Client 116 | 30 / 30 |
| Client 116b | 8 / 8 |
| Client 117 | 21 / 21 |
| Client 118 | 15 / 15 |
| New client 118b | 16 / 16 |
| Pure client 118b preflight | 10 / 10 |
| Isolated launcher mode/env checks | 6 / 6 |

Recovery includes the original 289 tests, five review-patch regressions and five
additional timing regressions. Focused patched-author tests also passed 44/44
(20 fingerprint, 10 precompute, 14 timing); those overlap discovery and are not
extra independent evidence. Launcher and client shell syntax checks passed.

Recovery command:

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python3 -B -m unittest discover -s experiments/ltx25-b70/recovery/20261009-continuation118b-stream -p 'test_*.py'
```

All historical client suites ran through
[run_cpu_suites.py](../stream/tests/run_cpu_suites.py), e.g. append `run_tests_118b.py`
to that script's venv-python command. Exact per-suite commands and evidence paths are
in the receipt. The adapter substitutes cooperative file-based shutdown/pause for
signals to its own fake children, blocks non-loopback connections and port 8188,
and forces every child to the same interpreter with -B. Interrupted-state recovery
was tested through cooperative child self-exit, **not operating-system SIGKILL**.
No real model endpoint was used. The 116 live-port rejection test parses 8188 but
rejects arguments before network access, under the socket guard.

An early development recovery run started before re-identification was complete and
finished 296/299 (two identity assertion failures and one stale-plan error). It is
not qualification evidence. The final inventory-matched complete run passed 299/299
in 626.273 seconds; all 289 original test methods remain, with ten regressions added.

Historical 114 X5 was stale: 114 is already sealed. It now verifies that the sealed
default manifest refuses a mismatched fake server before posting. Historical 118
must read its unchanged sealed modules, because the patched author sources correctly
fail its frozen module pins. An initial old-source-pin test failure was resolved by
that read-only test mapping; the complete legacy 118 rerun passed 15/15.

## What remains unproven and the first future launch

CPU tests close the four source-review findings. They do not establish XPU snapshot
performance/equivalence, capped decoder byte identity or allocator reuse, sustained
stability, memory headroom at 121 dg1, seam quality or any speed improvement. Conservative
P7 dual checking adds CPU work and may reduce the projected gain. No existing host fault
or owner-approval decision is cleared by this rebuild.

The measured comparison is 117 at 121 dg0: **5.40 s per 5.04 s video chunk**. Therefore
first use 121/frame/dg0/cone/1/1/fingerprint/no cap; second 121 dg1 cap1.0; third 97 dg1
uncapped. These are future choices, not a campaign launched here. Exact first command
from the repository root, text only, after separate authorization and fresh admission:

```bash
experiments/ltx25-b70/recovery/20261009-continuation118b-stream/launch-118b.sh 121 frame 0 cone 1 1 fingerprint - "$FRESH_HEALTH_RECEIPT"
```
