# Queue pin guard and one-card time accounting — October 18, 2026

Packet58x now refuses at planning when it borrows packet58w's mutable
`verify_ready.py`. The same check runs again just before a queue job launches.
A refusal saves explicit evidence that no launch or device work occurred,
drops dependent jobs through the existing queue completion path, and continues
to independent work. It does not try the refused job again.

This was CPU-only work on steve-b70s. No GPU job, service, driver, model read,
live queue edit, sudo command, or host setting change was performed. CPU probes
and tests used nice 19, cores 8–15 and 24–31, `python3 -B`, closed stdin, and a
2-GiB virtual-memory limit. Unrelated dirty and
staged work was preserved. `git pull --rebase` refused that dirty tree;
`git fetch origin` confirmed `HEAD == origin/main` before editing.

## Pin admission

Implementation: [pin_guard.py](../experiments/own-xpu-runtime/ops/lane-queue/pin_guard.py),
called by [lanequeue.py](../experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py).

- Read current build receipts, seals, source lists, pin maps and readiness
  metadata, including orchestration readiness and hash-linked packet metadata.
  Historical lineage snapshots are not treated as active manifests.
- Support repository, packet and seal-relative paths, nested maps, records
  with path/hash fields, compressed JSON source maps and checksum lists.
- Resolve symlinks before deciding whether a pin stays inside its packet.
  Reject an external mutable pin before invoking the packet's CPU plan.
- The explicit immutable exceptions are the packet49 oracle, targets recorded
  in `oracle-binding.json`, model files, frozen `screen/v4-lanes` wrappers,
  hash-pinned ELF/archive binaries inside parent build trees, and evidence
  beneath completed chain/window receipts. A source file in a build directory
  does not become a binary exception. Evidence-file symlinks cannot escape a
  completed evidence tree into mutable code.
- Stream SHA256 checks of non-model pins on each admission. Conflicting hashes
  remain separate obligations; edits during hashing refuse. Model content is
  **not read**: its existing model-identity gate remains responsible, and the
  guard explicitly reports deferred model hashes. This guard does not replace
  the packet's own seals or model gates.
- Planning emits its refusal receipt in the JSON result without writing into
  the packet. Running writes a unique `*.pin-refusal.json` in the queue directory
  and records `REFUSED-PREDEVICE`, with `launch_attempted=false`. No fake PID
  observation is needed: the queue has not started a child.

There is no separate enqueue command in this queue implementation. `plan` is
the preparatory admission interface, `run` invokes it again, and the final
prelaunch check catches edits during review or admission waits. The guard does
not make concurrent uncooperative source edits atomic; existing in-window
identity checks remain necessary. Existing running drivers were not restarted.

The real packet58x smoke proposal was checked with a CPU-plan invocation trap.
It refused and explicitly identified
`stage2/packet58w-onecard-record/verify_ready.py`, sealed by packet58x's build
receipt. The trap confirmed that the packet plan was never invoked. Other
borrowed mutable pins also refuse; the allowlist was not widened to grandfather
historical shared source trees.

At the final recheck, concurrent work had repaired packet58x's receipt: the
packet58w verifier entry was gone, and its current **333 pins passed** the
guard. The invocation trap then stopped before executing the packet plan, as
intended for this read-only probe. The original cross-packet case remains a
temporary-fixture regression test; the repaired packet is not falsely reported
as still refusing.

## Frozen briefs

[frozen_paths.py](../experiments/own-xpu-runtime/ops/frozen_paths.py) prints the
sorted union of pinned paths and their symlink targets for queued packets,
readiness markers, inflight jobs and live reservation owners. It includes the
pin manifests themselves. Ambiguous packet copies are all frozen; launch
admission still refuses to guess. An unreadable manifest or running owner
produces a nonzero exit and an incomplete-list diagnostic on stderr.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/frozen_paths.py </dev/null
```

The final read-only live discovery check found **23 packets and 46,455 paths**,
with no errors. It took 55.8 seconds and peaked at 122,348 KiB RSS. This is a
snapshot of the concurrently maintained metadata. Overlapping seal
maps are deduplicated by path/hash before retention; path resolution is done
once per distinct frozen path. An initial CPU probe exposed excessive repeated
map retention under the 2-GiB cap; that was fixed before the successful check.
No model content is needed to produce this list.

## Time accounting

[gpu_time_review.py](../experiments/own-xpu-runtime/ops/gpu_time_review.py) now
reads `packet*/evidence/card*-*/**/window.json`, including nested WSCREEN and
bracket windows, alongside the existing two-card build windows. One-card
windows hold both lanes, but only their selected card earns busy card-minutes.
Per-card interval unions remove overlap among queue, window and device
receipts. Available time is four cards multiplied by the report duration.
Unknown card identity is reported without inventing busy credit.

The new figure is **assigned-card occupancy**, not a hardware compute counter.
Queue lifetimes retain their existing occupancy meaning. A rank receipt naming
card 0 does not by itself turn a two-card job into a one-card whole-host hold.

The reader found all seven saved packet58w chain windows between 18:12 and
18:37 UTC and the three packet58v bracket windows ending at 18:04 UTC. Together
their window clocks contain 26.756958 card-minutes in a 60-minute/four-card
report (240 available card-minutes). This deliberately excludes interwindow
90-second waits. Queue lifetime evidence is merged separately. The archived
packet58v bracket job actually starts at **17:50:35.746775 UTC**, with WSCREEN
starting at 17:53:58; the review brief's earlier 17:43 boundary is not silently
invented as device work. Synthetic boundary tests also cover the requested
17:43–18:04 and 18:12–18:37 ranges.

## Validation

CPU tests cover the incident's cross-packet verifier, pure in-tree pins,
oracle exceptions, changed/missing pins, nested seals, source-list formats,
model-read exclusion, symlink escapes, mutation after planning, durable refusal
and dependency continuation, frozen-list discovery, actual saved chain clocks,
one-card accounting, clipping and receipt overlap. Existing queue/plan and
device-accounting regressions are included.

**184 tests passed:** 152 lanequeue/plan/pin tests, 10 device-accounting tests,
18 time-review tests and four frozen-list tests. `git diff --check` also passed.

```bash
python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops/lane-queue -p 'test_*.py'
python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops -p 'test_device_accounting.py'
python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops -p 'test_gpu_time_review.py'
python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops -p 'test_frozen_paths.py'
```

Run these with the same CPU affinity, nice value, stdin and memory bounds above.
The tests use temporary queues and mocked launch backends. No live queue is
used as a writable test fixture.
