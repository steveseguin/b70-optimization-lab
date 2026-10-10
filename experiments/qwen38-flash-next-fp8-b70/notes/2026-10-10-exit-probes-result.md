# Flash-Next exit probes and first-forward admission repair — 2026-10-10

**Both exit probes passed on this boot with the image UMD. The first-forward
probe did no device work: a harness path error refused admission.** This task
only repaired and tested CPU code and recorded the coordinator's saved results.
No container, server, GPU, health probe, systemd unit or LTX endpoint was operated.
Existing run directories, including their STOP files, were not changed.

## Saved results

All paths in the table are under `../reopen-20261008/runs/`. Card `23:00.0`,
image UMD `image-26.27.39122`, and image
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`
were held fixed for the two successful arms. They used the pinned
[owner acceptance](../../ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json)
and the 17:44:16 health receipt, saved with the evidence below.

| Run directory | Saved result | Gather / explicit sync / cleanup sync | Watcher |
| --- | --- | --- | --- |
| `probe-clean-exit-20261010` | Admission refused: watcher not started; no device work | 0 / 0 / 0 | Absent; retained as an invalid first attempt |
| `probe-clean-exit-20261010b` | Passed, complete, exact bytes, normal exit | 1 / 1 / 1 | Passed; zero new fault lines |
| `probe-exit-sleep-20261010b` | Passed, complete, exact bytes, abrupt exit after 10 s idle | 1 / 1 / 0 | Passed; zero new fault lines |
| `probe-first-forward-20261010b` | Failed during receipt construction at admission; no worker/device work | Not reached | 150 s bound, STOP; no FAULT.json |

The two passing watchers retained four excluded historical fault/reset lines;
“zero” means no new counted fault lines, not an empty historical kernel log.
Clean exit requested host-cache release successfully. Its before-exit marker is
17:45:48.184720 UTC. Sleep returned from device work at 17:46:20.236139 and reached
before-exit at 17:46:31.192889; the interval includes its fresh watcher handshake.
Both guardians recorded worker status 0 and a fresh post-worker journal read.
The first-forward log contains the `ValueError` for
`/probe/single_rank_slab_probe.py` not being beneath the `/repo/.../reopen-20261008`
package. The later watcher bound is a harness stall, not a GPU fault. The owner
reported the subsequent normal LTX relaunch; this CPU task did not inspect it.

[Evidence index](../reopen-20261008/evidence/exit-probes-20261010/index.json)
binds original paths and SHA-256 values to byte-for-byte receipt/log snapshots.
The shared kernel log is stored once. The initial no-watcher refusal is retained.
Successful receipt SHA-256 values:

- Clean: `6353f275dd7c615eb09cde61a8207225a7a7c54abba5986b925f2bba5f016878`.
- Sleep: `12574df08590fc4667b3e2ff72cdcca731a1ef403cc04001591498e2dc266921`.
- Failed first-forward: `515711b151bc27a2c329295c0667c368ff87607c75ee54342de72844e85aa498`.

## Interpretation against the preregistration

The [preregistered “Both clean” row](../reopen-20261008/probe/README.md#preregistered-interpretation)
applies: flakiness, another cause or changed state remains possible. Neither a
production change nor a safety certification follows. The teardown overlay
remains unqualified. Ten seconds of idle also changes timing, so this is not
a matched repeat of the original immediate abrupt exit.

**Both October 9 tiny probes released Python local references before exit.**
The image-UMD and host-UMD probes returned from `run_device`, dropping slab,
view, UVA, output/table/resident tensors and local aliases, then used `os._exit`.
Neither deliberately retained live tensor references. Native caches, mappings,
queues and context could survive; their lifetime was not measured. The
[October 9 source audit](2026-10-09-exit-lifecycle-analysis.md#what-actually-survives-the-original-worker)
corrects the earlier “all tensors still live” description.

Tonight's clean arm explicitly releases aliases, collects garbage, synchronizes
again, empties caches and uses normal interpreter exit. The sleep arm drops its
locals at the original return boundary, idles ten seconds, then exits abruptly.
Thus abrupt exit after release did not reproduce either October 9 fault tonight.
The earlier exit-boundary association remains evidence, but abrupt exit is not
shown to be a sufficient cause and native cleanup is not shown to be the cure.

Abrupt exit **without releasing references** (live slab/UVA/device owners at
`os._exit`) remains untested. It is a distinct proposed arm, not what the two
original tiny probes did. The current harness has no flag for it. Preparing it
would require keeping explicit strong owners through the exit instruction,
recording that boundary, and separate CPU review/preregistration/admission;
there is no runnable command for that arm today. The corrected one-layer
first-forward and the TP4 full load/96 allocations/PLE/model-output gates also
remain untested by this window.

## Repair and CPU validation

The first-forward receipt used `path.relative_to(PACKAGE)` for both package and
probe support files. The repository layout hid the error; separate `/probe`
and `/repo/...` mounts exposed it. Support digests now use stable logical keys:
package-relative names and `probe/<basename>` names hashed from the actual
probe mount. The overlay manifest, all package pins and geometry gates remain.
Source/identity collection now runs inside the admission exception handler.

A pre-worker exception writes an atomic `admission_refused` receipt with
`worker_started=false`, time, exception and “harness refused before device work”,
and latches STOP. The watcher recognizes only that explicit pre-spawn state,
after a new clean kernel read begun after refusal. It returns failure (2) with
the clear status instead of waiting 150 seconds. Fault admission still runs
first; existing STOP/FAULT evidence is preserved. Missing/ambiguous markers,
worker-started paths and native stalls retain the original bounds and postflight
requirements. No retry or kill path was added.

CPU suites: **lane 227 passed / 6 skipped; probes 84 / 1; teardown 49 / 0;
first-forward 37 / 0**. Zero failures/errors. First-forward is included in
probes: **360 unique passes, seven skips**, or 397 passes across 404 executions
including its separate rerun. The six lane skips exclude checkpoint/XPU
rehearsals; the probe skip excludes fatal SIGALRM. Tests ran nice 19 with
OMP/MKL/OpenBLAS set to 2 and the device-open guard; temporary scratch was
removed. The integration fixture mirrors `/probe`, `/repo/...`, `/receipts`
and `/health.json` below a temporary root, runs real admission with pinned owner
acceptance/overlay/geometry, denies runtime imports and stops at a mocked
guardian. It does not claim container or native qualification.
[Validation and logs](../reopen-20261008/VALIDATION.md#probe-mount-admission-repair-2026-10-10).

## Next arms — commands are text only

First admit the corrected one-layer first-forward in its own window. For exit
causality, separately admit a matched clean/immediate-abrupt pair, with the
same image UMD, card, allocator policy and indirect gather; the immediate arm
removes the ten-second timing change. A live-reference abrupt arm is the
additional design gap above, not a synonym for the default. No TP4 launch is
recommended from these tiny passes.

The supplied health receipt expires **2026-10-10 23:44:21 UTC**. Replace `health`
with a new passing receipt from the admitted boot/window if expired; nothing
here obtains health or extends acceptance. All proposed directories must be
NEW and empty before use; none was created or run by this task. Each arm needs
an exclusive coordinator-admitted idle window, the five-minute gap, and the
same owner acceptance passed to its host watcher. These are alternatives for
separate windows, not an unattended chain. The first fault ends submissions;
any refusal/STOP also ends that attempt. Do not overwrite or retry a saved run.

```sh
p=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008
health=experiments/ltx25-b70/data/resume-20261008/postflight-probe-window-20261010T174416Z.json
owner=experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json

# First-forward: new directory, corrected support hashing; printer only.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-first-forward-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-first-forward-20261010c" \
  --overlay-sha256 e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d

# Separately admitted matched clean repeat; printer only.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-probe-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-clean-exit-repeat-20261010c" --clean-exit

# Separately admitted immediate abrupt repeat AFTER local-reference release.
# No exit flag selects the original abrupt mode; this is NOT live-USM retention.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-probe-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-abrupt-immediate-20261010c"
```

For the selected arm, use the [coordinator sequence](../reopen-20261008/probe/README.md#coordinator-sequence)
with this exact watcher command and the same `health`, `owner`, and `receipt`
values. Start the watcher first and wait for its clean heartbeat before any
printed container command. This watcher invocation is also text only:

```sh
# Select exactly ONE of the new receipt directories above for this window.
receipt="$p/runs/probe-first-forward-20261010c"
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$p/probe/watch_kernel.py" \
  --health-receipt "$health" --owner-acceptance "$owner" --receipt-dir "$receipt"
```
