# Packet58ai: current one-card miss census

Preparation only. No queue or device launch is authorized by this packet.
The coordinator may schedule it only after both two-card queues are empty.
The record anchor is packet58ad, 30.396 tok/s, tile16, p60fusion, maximum
21,552,729,600-byte immutable expert cache, overlapped maintenance, zero-copy
misses, BF16 KV and the unchanged iq3-p49-split32-v1 oracle.

The complete tracked packet58ad copy is retained under lineage/packet58ad
and lineage, including symlinks. The root adapters derive from that copy;
the single-load bracket adapters come from its native parent, packet58ab.
The 148-file private native source closure is the source behind 58ad's
hash-bound 58ab executable. No old packet is modified. Immutable parent
object files are the only native build dependencies outside this tree.

The lab's packet58af partition mechanism is reused at its exact expert
kernel sites. This contribution is instrumentation, not a new optimization.
A0/A1/A2 disable profiling. B0 retains ordinary events around the ORIGINAL
mixed-residency launches. B1 measures disjoint resident and zero-copy
partitions on the same in-order queue, for every layer and position.
All five views use p60fusion and the same tile16/cache configuration.
Every view runs all 12 fixed prompts with a 128-token cap, in ONE load.
Each generated token is checked against the unchanged packet49 oracle.

Partitioning changes scheduling. B1's resident compute and miss service
are measured diagnostic intervals, not the original kernel's internal
stall cycles. B0 records the actual router-ready-to-expert-start window.
No subgroup-clock conversion is assumed: the installed experimental clock
has no portable time conversion or shared-device clock guarantee.
The analyzer must keep this distinction and report overhead against both
warm controls. These repeated views never supply a performance headline.

Event retention happens only when prepared commands are INVOKED, outside
capture. Queries happen after the existing token drain. Cache hit/miss IDs
are classified from the published pointer table and the existing route
readback, before cache observation changes. Fills are never counted as misses.

The final READY-FOR-DEVICE.json is written last and is the handoff authority.
Missing build, CPU quality, entry, pin, loader or report checks keep it false.
The diagnostic does not establish device equality or measured cost before it runs.

Retention: the requested source copy deliberately includes previously retained
archives/receipts over 1 MiB. lineage/58ad-copy.json identifies their original
bytes and commit; restore the tracked copy from Git. New build outputs are
ignored, rebuildable from build_engine.py, and capped at 300 MB. Preparation
uses nice19, helper cores, closed stdin, Python -B and at most 2 GiB.

CPU evidence: [build](evidence/build.json), [partition exactness](evidence/partition-cpu.json),
[miniature parent/reset comparison](evidence/reset-gate.json),
[tests](evidence/python-tests.json), [entry/admission](evidence/argument-gate.json),
[shared entry/report rehearsal](evidence/shared-entry-report.json),
[loader](evidence/loader.json), [temporary queue plan](evidence/queue-plan.json),
and [immutable input admission](evidence/pin-admission.json).
The [proposal](../../ops/lane-queue/proposed-p58ai-census-A.txt) remains outside
the live queues. Its model watchdog is 7200 seconds against an expected job
duration of at most 900 seconds. Queue and in-flight checks refuse other work.

After a coordinator run, `analyze.py <proposal --output>`
reads the sealed native receipts and checks the complete log closure, all
48 layers at each position, oracle/record tokens, control drift and overhead.
It writes no speed claim. The [plan](PLAN.md) defines both thresholds and the
meaning of the conservative ceiling. A future run rechecks memory, storage,
device ownership, fault review, unit identity and the closed environment.
The total write allowance is 1088 MiB while preserving 25 GB root free;
[storage evidence](evidence/storage-budget.json) explains the unchanged K1
allowance. These are admission requirements, not promises about future free space.

Packet58aib prepares a fresh 12 × 64 smoke first. S0 enables the existing
resident/miss partition diagnostic. On the first completed request, the real
analyzer requires nonempty counts, both kernel event partitions and router
events for overlap. It reads that request only, without a wall-clock deadline.
The five-view census remains a later separate proposal; smoke is diagnostic.
CPU preparation stops below 27 GB; device admission reserves writes above 25 GB.

Packet58aid repairs the WSCREEN sensor import with a byte-identical private
copy of packet58aj's `screen/device_memory.py`; `device-memory-provenance.json`
records its hash. `device_import_gate.py` runs through `window.py` with Python
`-B`, the repository cwd and the real closed environment for K1a, K1b,
WSCREEN smoke and census. It imports the dependency closure, executes the
sensor with synthetic process observations, forbids device/model access and
rejects the missing-module regression. The two excluded missing imports are
unused standalone helpers (`launch_env.check_binary` and
`supervision.finalize_r1`), not window call paths.

The fresh smoke proposal is `packet58ai-census-d-smoke-A`, writing
`evidence/card0-census-d/smoke`. The separate
[conditional five-view proposal](../../ops/lane-queue/proposed-p58ai-census5-A.txt)
is `packet58ai-census-d-five-A`, writing `evidence/card0-census-d/combined`.
`verify_ready.py` recomputes the smoke's exact outputs, clean window receipts,
build identity, complete file hashes and all twelve real census streams before
that proposal can launch K1a. No stored readiness boolean is sufficient.
The failed c-smoke remains historical evidence; it contains no completed model
request and cannot provide positive device validation for the analyzer.

Native operation waits now explicitly use the existing `--wait-seconds 600`
option. This exceeds four times the recorded parent's longest cold first-token
phase; the five-view admission rechecks the same ratio against the new smoke.
There is no in-run wall-clock data-proof deadline. The 7200-second whole-window
watchdog and graceful ownership/cleanup rules remain. No native rebuild or
arithmetic change was made. Shared entry rehearsal reports the missing native
preparation harness and unclassified identity uses as warnings; the local
six-path launch and four-path import probes supplement, but do not relabel,
that missing full-shape device-define preparation proof.

`prepare_handoff.py` repeats CPU checks, both proposal rehearsals/plans and
pin admission, then writes `READY-FOR-DEVICE.json` last. It runs at nice 19 on
helper cores with closed stdin and checks peak RAM below 2 GiB. The marker's
smoke-ready status is preparation only; census5 stays conditional until the
fresh smoke and analyzer pass on actual device data. No queue is changed.
