# Continuation packet 123: more room and atomic previews

Packet 123 is a CPU-prepared successor of 122. Its optional residency change
makes 169-frame chunks a memory-admissible candidate on paper: 168 new frames
at 24 fps give **7.0 seconds of new video**. It is not a measured speed or an
adopted quality result. The coordinator's live 121 server was not operated.

The [full census and alternatives](2026-10-10-continuation123-residency-analysis.md)
identify the smallest complete-owner move: the 0.927351 GiB upsampler from 0
to 2 and the 0.339622 GiB audio VAE/vocoder from 3 to 2. The sampler stays 20/28;
text stays 24/24 on 2/3; the entire video VAE stays 3. The option's disabled form
retains 121/122 residency. Rebalancing the sampler 18/30 or 16/32 overloads 1 and
does not solve 3. Moving text or splitting the video encoder needs more changes.
The census binds safetensors headers and receipts, distinguishes registered
weight bytes from graph/static allocator residuals, and retains every measured
phase envelope. Exact isolated graph-pool/workspace sizes are unavailable.

`LTX_AUX_RESIDENCY=legacy|xpu2` is an environment option on the unchanged122
positional launch grammar. Retargeting occurs before model load. It changes
neither numerical kernels nor precision. A distinct residency qualification
identity binds the option and target devices alongside the unchanged numerical
ID.169 is restricted to xpu 2 auxiliary residency, dg 0, frame/cone,
two-way 20-28 and display 3. Auxiliary plus display replica is refused; 145 dg 1
replica is refused too. All original ownership, source, fault, no-eviction,
three-chain and per-chunk cone/display checks remain. Auxiliary operations
reserve 2 GiB workspace above the 2 GiB floor plus.75 GiB screening margin before
execution and require 2.75 GiB free afterward. Shared counters are not called
isolated peaks.145 is additionally compared to the real 121 eager qualification's
seven output hashes per chunk, including the waveform. Its exact source
verdict and six receipts are sealed as provenance. CPU fakes cannot establish
full-model cross-device identity, and 169 has no safe legacy oracle run.

## Preview race

The 04: 34 UTC coordinator entry reports a strict identity-check failure and a
healthy server. Source inspection refines the diagnosis: the HTTP preview route
serves a JSON receipt, which previously became visible during `write_exclusive`.
The MP 4 already used a temporary file, but published by hard link then unlink;
a reader could see its link count/ctime change. The entry alone does not prove
which MP 4 write was active. Both publication windows are now closed.

The new writer fsyncs a hidden temporary file in the destination directory,
then uses Linux `renameat2(RENAME_NOREPLACE)` and fsyncs the directory. It never
overwrites a final name. Both JSON and MP 4 use this path. The original strict
reader is unchanged. An identity failure on a preview receipt may be retried
once after 50 ms only while the worker has not committed it. Completed evidence,
symlink, multiple-link and oversized-file violations remain errors. A failure
to obtain exclusive atomic publication closes the writer; there is no unsafe
fallback. Deterministic CPU tests reproduce appending-during-read and the old
hard-link window, and verify atomic visibility, strict completed-file failure,
collision behavior, fsync ordering and bounded retry.

On exit 7 the client preserves the HTTP 500 and original exit code, records one
status observation with a two-second socket timeout, and stops. Healthy,
faulted and unavailable status observations are distinguished. It neither
retries the failed request nor cycles the server. The status is an observation
after the failure, not proof of what happened before the request.

## Coordinator comparison order (text only)

No command below was executed, checked live or queued. Detailed command syntax
is in [LAUNCH.md](../recovery/20261010-continuation123-stream/LAUNCH.md).
Margins are GiB above 8/8/2/9 floors, in card 0/1/2/3 order. Aux rows include
2 GiB of destination workspace allowance and credit no removed source workspace.

| Arm, all dg 0/display 3 | Period forecast | Seconds per new video second | Card margins |
|---|---:|---:|---|
|145, legacy, atomic preview control|5.45–6.10 s|0.908–1.017|1.270 / 1.828 / 9.706 / 1.850 (measured 121 reference)|
|145, auxiliary xpu 2|5.45–6.20 s|0.908–1.033|2.198 / 1.828 / 6.439 / 2.189 projected|
|169, auxiliary xpu 2|5.95–6.65 s|0.850–0.950|1.620–1.930 / 1.574–1.711 / 6.439 / 0.825–1.557 projected|

Qualify 145 against legacy first; confirm actual physical-free savings and
retained reservations before considering 169. A weight move need not produce
the full predicted physical-free benefit.169's low xpu: 3 estimate exceeds the
required .75 GiB by only .075 GiB. Do not weaken a floor when an arm refuses.

The 97/121/145 scaling gives 169 sampler A about 1.95–2.15 s, sampler B 1.85–2.05 s,
eager cone .85–1.10 s and residual costs about 1.10–1.30 s. These are fits across
different sessions, not measured 169 values or independent quantities to sum
without accounting for overlap. Central period is about 6.2 s (0.886 s/s).
Moving the two auxiliary owners changes existing CPU-transfer destinations;
it adds no required peer hop. Even pessimistically treating all 3, 683, 072
transferred bytes as new costs .00037–.00368 s at assumed 10–1 GB/s; allow 0–.10 s
for dispatch/contention, not a measured bandwidth claim.

Display 169 is estimated 2.72–3.30 s (simple 145 frame scaling: 3.170 s), so a separate
three-second display target remains unproven. The inherited `GO_BOUND_S=3`
actually bounds waiting for the successor, not decode execution; it is unchanged.
A replica does not make the same decoder intrinsically faster. Its projected 169
transient is 4.101–5.639 GiB; the 6.5 GiB design allowance plus auxiliary workspace
would leave **−1.057 GiB** on 2 above its floor. Replica+aux is therefore not
admitted by 123. Tighter measured non-overlap would be a later packet.

## Seal and validation

Final packet, manifest, exact CPU counts and verification records are recorded
in [continuation123-build.json](../data/resume-20261008/continuation123-build.json).
The seal and test summary will be completed after the full CPU suites finish.

Open device-dependent work: actual allocator savings, isolated/colocated peaks,
full-model cross-device byte equality at 145, all 169 measurements and the
three-second display target. No GPU API, real model request, server launch,
check-only, xpu-smi, systemd operation, port 8188 connection, process signal,
render-device open, existing-run/live-client write or host setting change was
performed. Every Python invocation used the baseline venv's `bin/python -B`;
CPU tests use guarded child processes and at most four OpenMP threads each.

## New coordinator follow-up: storage allowance

CURRENT.md gained a 05:08 UTC entry while this packet was being sealed. The
inherited guard measures the entire filesystem's free-space decline against a
3 GiB allowance. Unrelated writers can stop a healthy stream; unrelated deletions
can also hide its growth. Packet 123 retains that guard and its independent
50 GiB free-space reserve. This issue is not fixed by the residency or preview
changes and remains a separate follow-up.

A focused successor should count retained allocated blocks in all run-owned
paths: the run directory, preview directories including hidden temporary files,
qualification validation outputs and owned request records. Preserve path and
identity checks, the 3 GiB allowance, the 50 GiB reserve and the raw-capture
bounds. Qualification captures alone can reach about 0.982 GiB at 145 frames
or 1.144 GiB at 169, so counting only previews would weaken the guard. A larger
allowance merely postpones the accounting defect. No storage guard was relaxed,
no evidence was deleted, and no coordinator operation was performed here.
