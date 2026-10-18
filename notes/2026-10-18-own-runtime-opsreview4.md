# Opsreview4: admission waits and CPU device-entry rehearsal

October 18, 2026, four-card host. CPU-only tooling work; no GPU work,
service launch, live queue edit, sudo, model read or host setting change.
Existing packets and unrelated orchestration edits remain untouched.

## Time accounting

`experiments/own-xpu-runtime/ops/gpu_time_review.py` now splits each queue
lifetime at its first device-entry evidence. It uses the output directory's
birth time, a window's recorded UTC start, native/rank log birth time, or an
observed device child. It never substitutes mtime or ctime for creation.
Older/reused outputs and explicit CPU/refused windows do not establish entry.
An unobserved entry earns no busy credit and is labeled unconfirmed waiting.

The packet141b archived receipt starts at **19:32:12.399043 UTC**. Its output
directory was created at **19:56:48.092595 UTC**. Its receipt ends at
**20:01:06.704363 UTC**. The corrected attribution is **24.5949 minutes of
admission wait** and **4.3102 minutes of device-backed occupancy**, rather
than treating the whole 28.9051-minute unit lifetime as busy. The original
review rounded the wait to 24.5 minutes; the retained clocks round to 24.6.

Evidence: `ops/lane-queue/done-B-reviewed-20261018T200131Z.txt` and
`stage2/packet141-transfer-gap/evidence/probe-B-repair141b/`, relative to
`experiments/own-xpu-runtime/`. Review 30 in `ops/review-log.md` identifies
the stale `hold-lane-B`. That historical cause is not in this job's machine
receipt, so the tool correctly reports `unknown` for its cause. Explicit
receipt/event blocker fields are grouped when available; a synthetic replay
also verifies the named `hold-lane-B` case. Current markers are never used to
invent historical causes.

Total per-lane admission wait is reported even when it overlaps another job's
work or whole-host hold. `idle_admission_wait` is the portion where the lane
was otherwise idle. Duplicate receipt/event evidence is unioned. Occupancy
remains a proxy, not a hardware compute-utilization counter.

## Launch environment and rehearsal

`ops/launch_env.py` records the exact working oneAPI library order, including
`umf` and `tcm`, with the source file and SHA256 in its header. Its checker
fails for any `ldd` "not found", even with exit status zero. New packets can
import or vendor it with `ops/entry_sandbox.py`; frozen packets are unchanged.

`ops/rehearse_entry.py <proposal>` reconstructs the actual lanequeue command
and closed environment under the exact `screen-<job>` name without executing
the command or starting a service. It verifies native build hashes, checks
each binary's dependencies, and runs its own help/version/argument parser.
Explicit packet library-path overrides are tested as well. It does not import
packet code or execute its device/plan command. JSON reports retain each
binary's failure phase and exit code without printing environment values or
unfiltered native output.

Probes use nice 19, CPUs 8–15/24–31, closed stdin, a 2-GiB address-space cap,
bounded time/output and a read-only Landlock allowlist. Model files and device
nodes are denied. Intel's allocator needs its own `/proc/self/maps` metadata
before main; a first bounded probe exposed that requirement. The allowlist
now grants only that process's maps file, not process memory or device fds.
No unsandboxed fallback is provided.

The real packet141c proposal passes both native binaries' loader and parser
checks, including its compiler-only override. Packet58x smoke-d passes all
five loader checks and three parser entries; its two cache-fixture programs
need explicit safe parser probes, so that proposal conservatively reports
FAIL. No packet was repaired or resealed by this task. Script coordinators
also require a packet-specific inner-environment rehearsal and fail rather
than guessing. New proposals can declare probes in
`plan.entry_rehearsal.binaries`; see the tool's docstring.

The appended hourly checklist requires this entry rehearsal **and** a CPU
run of the real arm sequence through prepared launches, resets and state
transitions. A loader/parser pass alone never certifies that sequence.

## Validation

48 focused CPU tests pass, including the packet141b timing replay, duplicate
and overlapping holds/waits, creation-clock handling, closed environments,
stale binary refusal, real ELF loading, a compiled missing-library fixture,
denied model/device reads, and native version/argument probes.

From `experiments/own-xpu-runtime/ops`:

```sh
ulimit -v 2097152
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest \
  test_gpu_time_review test_device_accounting test_launch_env test_rehearse_entry </dev/null
```

The real one-hour time review also reports packet141b's 24.6-minute wait and
4.3-minute occupancy. No performance or readiness record was promoted.
Git pull initially refused the unrelated dirty tree; fetch showed local main
ahead with no incoming commits. Before the scoped commit, another fetch
confirmed HEAD equaled origin/main at `4918800df49f7ff3cadcc7f8975e5758903351bd`.
