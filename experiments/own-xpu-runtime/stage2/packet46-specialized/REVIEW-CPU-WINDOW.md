# Independent CPU and window source review

2026-10-17, before the 02:55 UTC compilation cutoff. Read-only review of the
CPU expert arithmetic, fixtures, throughput runner, cache budget, preparation,
window admission and result summarizer. No compilation, sustained test,
accelerator query, device execution or model-payload read was performed.
Eight short mocked window tests were subsequently run and passed in 0.667 s.
This is a source review, not a compiled qualification receipt. The kernel
composition has a separate independent review.

## Arithmetic and fixtures

The AVX2 implementation preserves eight independent SG32 logical lanes per
vector, eight consecutive weights per lane, increasing tile/element order,
separate FP32 multiply/add operations, and the adjacent SG32 reduction tree.
K=640 inactive tail lanes skip additions. Gate/up BF16 materialization,
packet39 deterministic activation and down BF16 output boundaries match the
read-only packet45 P28/P33/P39/P42 functions examined. No arithmetic mismatch
was found in that source comparison. Compilation and raw-bit tests remain
necessary; this statement does not qualify an unbuilt binary.

The G4 fixture generator agrees with packet45 p39_fixture_data.hpp: seed and
LCG steps, expert-slice offsets, restored finite scales, peer XOR, and input
values. Expert IDs 0, 37 and 333 are existing fixture-bank slices. The two
P28 finite scale-edge rows agree with weights(T,2560,1,1,salt). No external
checkpoint bytes are needed. Complete expert comparisons cover BF16 gate,
up, activation and down; sampled rows also compare FP32 lanes and reductions.
Dedicated signed-zero/subnormal down-row probes would strengthen edge coverage.

Nonfinite scale/input rejection is explicitly candidate behavior. The code
and documentation retain nonfinite_oracle_qualified=false. Complete device
exceptional/status parity, real-weight admission and integrated CPU/GPU slot
ordering remain open. They cannot be inferred from the finite CPU test.

## Throughput and capacity scope

The 144-expert packed fixture bank uses the stated 47:1 format mix and exceeds
the aggregate L3 capacity. Timed work includes complete expert arithmetic,
input permutation, result validation/hash and OpenMP dispatch. Reported packed
GB/s is processed bytes, not measured DRAM bandwidth. Independent expert
parallelism is explicitly more permissive than the dependent ten-slot model
layer; no engine speed follows from it. The default two fresh processes and
five samples of at least two seconds need actual after-cutoff receipts.

The cache budget uses metadata only, preserves packed formats and full BF16
KV, includes alignment/metadata, separates the 30 GiB arena from the physical
reserve, and corrects the prior PLE-history count. Uniform hit/miss requirements
are labeled scenarios. Live allocation peak, complete speculative rollback,
CPU miss tails and actual IQ3 routing remain unresolved.

## Findings sent to the implementation agents

1. **Worker affinity:** the first reviewed benchmark checked the main-thread
   mask only. OpenMP affinity controls can alter worker masks; check every
   worker inside the existing environment guard, or close those controls.
   Do not rely on taskset as an immutable cpuset fence.
2. **Native receipt ABI:** the first reviewed layer receipt omitted top-level
   safe_to_exit while the summarizer required it. Derive it from all owned
   device teardown results. The kernel agent is addressing this.
3. **Complete capture validation:** the first summarizer accepted one
   intermediate per case. Require the frozen complete capture manifest,
   including full mutable allocations, and reject missing/duplicate ranges.
   The main agent is addressing this with the kernel agent.
4. **Exactness companion closure:** timing-pair summary initially compared
   companion metadata without reopening its referenced receipts. Re-hash
   companions and re-run prerequisite validation before declaring a later
   integration candidate. The main agent reports this has been added; the
   final version still needs its negative tests and review.
5. **Retained child lifetime:** coordinator units must explicitly avoid
   systemd control-group cleanup killing a GPU child after supervisor exit.
   The planned runbook must preserve KillMode=process, SendSIGKILL=no and
   suitable remain-active behavior, with no runtime hard-kill deadline.
   The runbook was not yet present at the review boundary.
6. **Cached object provenance:** packet45 receipts bind final binaries,
   compile/link commands and sources, but not .o hashes. Recording present
   objects alone does not prove they produced that pinned binary. The kernel
   agent has been asked to establish this, for example through an after-cutoff
   deterministic relink to a temporary packet46 output and comparison with
   the sealed baseline. Never modify packet45.

The preparation cutoff, nice/affinity checks, packet-local exclusive work lock,
8 GB remaining-storage floor, coordinator-only card-0 admission and inherited
save-before-cooperative-stop supervision are present in reviewed code. Busy
children are not force-killed by that Python supervisor. Final runbook,
seal closure, negative admission tests, compiled CPU results and throughput
receipts were unavailable at this review boundary and remain pending.

## Final pre-compilation follow-up

Refreshed review after the runbook, command files, CPU gate runner and seal
were written. The original findings above are retained as review history;
their present source status is:

- Worker affinity is now checked on each OpenMP worker at admission and each
  measured sweep, and per-worker masks are recorded. CPU percentile reports
  now use observed nearest-rank samples.
- Native receipt now derives safe_to_exit from all started owners completing
  the existing shutdown routine; that routine throws or retains an owner when
  its safe teardown gate fails. Full capture manifests and complete mutable
  allocation snapshots are emitted. All 420 timing pairs additionally compare
  complete restored-state outputs and require no sticky error.
- Exactness validation compares the entire ordered capture manifest frozen by
  two equal CPU-owner runs. Missing, extra and reordered byte ranges fail.
  Timing-pair summary re-hashes both exactness companions and revalidates their
  complete native-file identities and fresh owner/boot/environment identity.
- WINDOW.md uses explicit KillMode=process and SendSIGKILL=no, with no
  RuntimeMaxSec or restart policy. The command files preserve a closed runtime
  environment, nice 19 and cores 4–15,20–31. A retained child is explicitly the
  coordinator's responsibility; the runbook instructs against advancing.
- The build now requires an unchanged-parent relink into packet46 to reproduce
  the sealed parent binary before reusing dependency objects. Original and
  generated source/mirror identities are checked, with input hashes checked
  again after compilation. This closes the provenance issue in design; the
  actual relink proof remains an after-cutoff build gate.
- cpu_checks.py explicitly pins the inherited packet34 window supervisor.
  seal.py merges that identity with the complete named CPU gate set, host and
  device build receipts, candidate artifacts, exact capture manifest,
  coordinator command files and preregistration/runbook.

The refreshed test_window suite ran eight tests in 0.667 seconds, all passing,
with journal/process/device interaction mocked. It covers admission, changed
sources, fresh companions, retained-child supervision, complete timing-event
accounting, missing captures and a mocked complete window. No compiler or
native executable was started. No GPU or model-weight access occurred.

No unresolved blocking source finding remains within this review's CPU/window
scope. This is conditional on the subsequently generated build, relink and CPU
gate receipts passing under these exact sources. Compiled CPU exactness,
throughput, device qualification, measured 80-microsecond savings, actual cache
fit and complete engine integration remain unmeasured at this review boundary.
