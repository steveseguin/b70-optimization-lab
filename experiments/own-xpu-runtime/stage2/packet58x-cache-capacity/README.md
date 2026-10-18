# Packet58x: larger immutable expert cache on one B70

CPU preparation for a coordinator-owned smoke, followed by a one-load bracket.
This packet makes no new speed or quality claim. The target arithmetic remains
`iq3-p49-split32-v1`, with tile16 expert down weights, target-only decode,
4,096-position BF16 KV and zero-copy expert misses.

[Admission and independent replay](ADMISSION.md) permit **21.5527296 GB** of
cache, compared with the 18 GB control. The estimate clears the registered
gate narrowly: **+2.26%**, conditional on the independent miss ratio and the
25 GB/s fill-copy proxy. The speed and native hit rate must be measured.

## Implementation

The source is copied from frozen packet58v. `copy_parent.py` copies links as
links; the parent has zero symlinks. Generated builds and completed parent
verdicts are not inherited as new results. The copy retains packet58v's
drain fix, real lanequeue unit gate, closed environment, `getrlimit` checks,
recorded oneAPI library path and original oracle binding. Frozen packet58j
kernel objects are reused only after relinking both parent executables and
matching their recorded hashes. External oracle links remain under
`oracle-binding.json` and `shared_oracle.py`; they are not flattened into
the source closure.

There is one maximum-size device arena per model load. `cache_cap=18GB|max`
changes the usable extent inside it. Every transition drains foreground and
maintenance work, finishes any pending publication, invalidates all residency
entries with new generations, publishes host pointers, and retains allocation
IDs and addresses. The view starts empty; immutable expert weights may persist
between its twelve requests, but never prompt/KV/response state. Actual fills
copy the same pinned bytes into the existing arena. No weight layout or
arithmetic changes at a boundary. A native and Python check compares every
output token with the original packet49 oracle.

`cache_maintenance=serial|overlap` remains selectable from queue, window,
suite and native commands. It is fixed across a capacity bracket. The sealed
[maintenance decision](maintenance-decision.json) selects overlap only if the
completed packet58v bracket rechecks exact and faster; otherwise serial.

## Memory and lifetime gates

Both usage settings reserve the maximum allocation. The host requirement is
**98,989,727,744 bytes**, including full backing for the added cache, the
unchanged 4 GiB margin and 8 GiB reserve. The 4 GiB live shadow stop is unchanged.
The device allocation bound is **29,963,128,848 bytes**, with a separate
512 MiB driver allowance and the unchanged 1.5 GB reserve. All prior KV,
workspace, transaction, fill and pointer-table allowances remain. Native
allocation calls and planning use the same new bound. Native after-load
admission and the live supervisor both reject DRM occupancy above 30.5 GB.
The full-shape mock reserves the real maximum extent without touching model
payloads and switches both caps under both maintenance modes at contexts 32
and 4096. It cannot prove device fit or speed.

## Proposed device work

Only the coordinator may run the two named proposals, after their final seal
and readiness marker exist:

- `ops/lane-queue/proposed-p58x-smoke-A.txt`: two K1 fixtures, then one model
  load and twelve 64-token requests at `max`. Expected 600–900 seconds.
- `ops/lane-queue/proposed-p58x-v5-A.txt`: two K1 fixtures, then one load with
  18GB/max/18GB/max/18GB, twelve 128-token requests per view. Expected
  1200–1800 seconds. It refuses without the exact smoke and clean teardown.

Both require card 0, lane A, whole-host ownership and lane B paused/drained.
Both use a 7,200-second watchdog, at least four times the upper estimate.
Temporary queue planning does not enqueue either job. A one-process bracket
is screening evidence; fresh-load determinism and the strict 512-token final
gate remain separate requirements. No record chain or submission is prepared.

## CPU reproduction

From this directory, prefix commands with
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`:

1. `admission.py` (analysis from completed receipt inputs).
2. `restore_fixtures.py`, then `build_engine.py` (all compilation uses the
   shared `ops/compile_turn.py`; it waits during whole-host device work).
3. `protocol_gate.py`, `k1_gate.py`, `cpu_gates.py fullshape`,
   `cpu_gates.py reset`, `startup_gate.py`.
4. `plan_queue.py --emit-only`, `argument_gate.py`, `run_cpu_gates.py`,
   `shared_oracle.py --require-complete` to `evidence/oracle-gate.json`.
5. `seal.py`, `seal.py --verify`, `plan_queue.py`.

Only CPU CLI processes install address-space limits. Sparse full-shape tests
and intercepted launch probes need unlimited virtual addresses and retain
less than 4 GB resident memory. Root must retain 25 GB free; the build cap is
300 MB (the inherited builder enforces a stricter 200 MB). Never import a
CPU cap into the device launch path. Do not copy readiness from another packet.

Hot-expert cache idea credit: **Niko1221 / Strata**. All implementation is
lab-authored. [Task note](../../../../notes/2026-10-18-own-runtime-packet58x.md),
[boundaries](DO-NOT-REPEAT.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
