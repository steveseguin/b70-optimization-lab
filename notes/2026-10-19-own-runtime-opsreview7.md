# Opsreview7: catch packaging failures before lane entry

The entry rehearsal now catches the bad storage floor and data-proof deadline
that stopped packets154 and153. It also runs packet151's retained CPU preparation
fixture with the saved real rank arguments. The old fixture fails at native
preparation; the repaired fixture reaches its decode positions and passes.

Both default and `--report` modes return `storage_floor`, `wall_deadlines` and
`preparation_path` JSON checks. Any FAIL blocks the combined result. Missing
preparation declarations produce `WARN: no preparation-path probe declared`;
this warning does not block otherwise passing legacy packets. Text mode prints
each FAIL/WARN; JSON mode sends those lines to stderr and keeps stdout valid JSON.
The brief checklist now requires new packets to declare a preparation probe.

## What runs

- The source walk follows local imports and literal pathlib worker/report paths
  inside the job's packet. It excludes `lineage*` copies, build tools and CPU
  test/gate scripts. It does not import the packet in the parent process.
- Storage comparisons resolve numeric constants and simple arithmetic, require
  25,000,000,000 bytes, and compare the stated GB/GiB message with the value.
  Inline comparisons are replayed at 25.5 GB plus planned writes. Named storage
  helpers are imported in separate guarded children and called unchanged with
  patched `shutil.disk_usage`; unsafe/unsupported imports are recorded as WARN
  replays, never represented as executed functions.
- Wall limits use a 60-second measured cold first-request baseline, plus the
  longest matching load/TTFT measurement in small saved JSON receipts for the
  proposal's output or `entry_rehearsal.timing_evidence`. Planning estimates are
  not measurements. Limits below twice the matching duration fail. Data-proof
  wall limits fail even above that threshold or when their bound is dynamic.
  Systemctl, admission barriers and teardown are not compared to request TTFT.
- `plan.entry_rehearsal.prepare_probe` (also accepted in a build receipt) declares
  a native command, its real `rank_argv`, binary SHA256, completion marker,
  optional small metadata/source pins and temporary-output environment key.
  Arguments after the executable must match exactly. The transport-only CPU
  fixture must use the device preparation defines and reach first decode before
  emitting its completion marker. Missing or unsafe declared probes fail.
- Packet151's existing `v5/evidence/preparation.json` supplies the legacy adapter:
  it checks the saved argv against the pinned rank0 launch, verifies its source
  pins, and runs the existing fixture without rebuilding. The native sandbox
  grants installed libraries, the exact metadata files and temporary writes.
  It also grants the tracked 4 MiB packet136 rotary sin/cos **source table**,
  SHA256 `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
  This is a frozen source lookup table, not checkpoint weights. Model directories,
  device nodes and live packet writes remain denied.
- Packet151's real report reader needs sibling/proposal timing streams. Its
  temporary synthetic fixture now supplies them, with no replacement of the
  analyzer or its checks. Its new `checked_smoke` prerequisite is substituted
  at the same prior-device-evidence boundary as the older `load` prerequisite.
  Report results remain explicitly synthetic, not device/quality measurements.

## Replays and checks

| Case | Result |
| --- | --- |
| packet153 `3813d8dd9^` analyze blob `4935fdb7fb65a34954a3c6bb13e7d0158863cce9` | Both 60-second data-proof deadlines FAIL |
| packet154 `80d3d7434^` screen blob `82e0172c250510caefde269f9bc4ac1f30efe5f1` | Both 30 GB checks FAIL; their 25 GB messages disagree |
| packet151 pre-fix source tree `c7cea2b08e77defd0eadc94e25d37e3a66cf33dd` | WARN: no preparation-path probe declared |
| packet151 retained old CPU preparation binary | FAIL; native preparation bypass reproduced |
| packet151 retained fixed CPU preparation binary | PASS through real-geometry decode positions |
| Current packet151 smoke proposal, default and report modes | PASS all three new checks; smoke/bracket reports pass |
| Current packet153 and154 smoke proposals, both modes | PASS; preparation declaration remains WARN |
| Current packet58ai entry source | FAIL for its retained 30 GB storage floor |

The historical tests use `git show` and temporary source copies; they never
check out or edit packet trees. The old/fixed native fixture regression skips
only on machines without the retained binaries; it ran on this host.

Validation: 35 rehearse tests and 96 lanequeue tests. Coverage includes literal
and dynamic proof deadlines, timeout/deadline arithmetic, measured-phase maxima,
message/value disagreement, actual storage function replay, unsafe import
refusal, both CLI formats/modes, rank argv mismatch, and a native sandbox check
that admits one metadata file while refusing a neighboring synthetic model file.

Commands, from the repository root (each with stdin `/dev/null` and
`ulimit -v 2097152`):

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops -p test_rehearse_entry.py
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops/lane-queue -p test_lanequeue.py
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/rehearse_entry.py experiments/own-xpu-runtime/ops/lane-queue/proposed-p151-smoke-B.txt --report --json
```

The same proposal check ran for p153 and p154, with and without `--report`.
Temporary receipts/logs are `/tmp/opsreview7-p{151,153,154}-{default,report}.json`
and `.log`, `/tmp/opsreview7-tests.log`, and `/tmp/opsreview7-lanequeue.log`.
The tests and pinned historical blobs are the durable replay evidence.

## Limits and scope

This is a bounded packaging rehearsal, not a Python/C++ whole-program verifier.
Computed import paths and phase names outside the recognized source/timing
forms need an explicit declaration or adapter. A missing load measurement does
not invent one. The preparation fixture proves registration/dispatch, not model
arithmetic or quality; the separate real CPU arm-sequence gate still applies.

CPU only on `steve-b70s`, nice 19, CPUs 8–15/24–31, at most 2 GiB address space
per child, closed stdin, no checkpoint reads, GPU work, services, sudo or host
setting changes. Packet trees and queue files were not edited. A first attempt
at the native fixture correctly failed when the rotary source input was absent
from its sandbox; no device access was permitted. A bounded tracing attempt was
inconclusive and timed out inside that same CPU sandbox.

The initial pull refused unrelated dirty work; fetch confirmed HEAD equaled
origin/main (`c09c3d2051adcc136dbd695a2f84ae753e8cb819`). Other work advanced the
shared main branch during this review. Only the four authorized paths belong
to this change; use a path-only commit and push it immediately.
