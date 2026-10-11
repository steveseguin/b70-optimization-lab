# Packet19: CPU dependency and ownership checks

CPU-only audit of packet16's two-card resident decode after the captured fault.
Original packets13–18, CURRENT.md, stage2/README.md and SCOREBOARD.md were not
edited. No GPU binary, discovery, device node, parked process or service was used.

**The native root cause remains unproven.** The owner already creates one total
event chain across both cards. We reproduced unwritten snapshot readback bytes;
we did not find a missing application edge or foreign compute binding.
[Every shipped-path violation](VIOLATIONS.md) is listed separately. The
leading unproven candidate is native cross-device event/backing behavior.
[Ranked findings](ROOT-CAUSE.md), [independent audit](review-hazards.md),
[packet18 integration](INTEGRATE.md), [patch series](fixes/series), [arm closeout](closeout.md).

## Checker

`depcheck.hpp` implements allocation ownership/context, sparse byte initialization
intervals, per-range last writers and all outstanding readers, transitive event
ancestry, host fences, and pending allocation/event/queue lifetime checks. It
reports RAW, WAR, WAW, foreign bindings and never-written reads. Copying poison
preserves it. Poisoned index inputs and unsafe frees fail before executing a
closure. Reports identify the site, allocation and required writer/reader edge.

`instrument.hpp` supplies the operation read/write/index contracts. Pool and
attention scratch ranges are tracked by bytes where cheap; general matrix and
interpreter reads use conservative allocation extents. The backend checks even
unused bound pointers, matching the native Context ownership check. Host slab
writes are explicit and checked against outstanding readers. Shared peer copy
is the only device-to-device ownership exception.

The scheduler queues concrete operation objects by value and runs a randomized
ready node at host waits, respecting ONLY declared event edges. Seed0 selects
submission order among ready nodes; seeds1,17,73 are the runtime adversarial gates.
The actual owner is included by path; every operation still passes through its
Device::compute/CopyEngine::copy. The final CPU harness replaces only
hold_for_supervisor with a report-and-exit path: pending CPU closures are
reported as canceled, never executed or marked complete. This prevents the
native retained-owner safety policy from hanging a negative CPU test; it is
not a patch to the native owner. A total chain has only one ready
node, so these seeds legitimately keep its order. Negative tests remove edges
and demonstrate both sanitizer failures and numerical mismatches under 32 seeds.
No implicit same-queue or submission-order edge is invented by the checker.
The real-weight gates retained the untouched owner. Final integration gates
repeat against the CPU fatal-path overlay; source equality receipts bind all
numeric translation units to the real-weight-tested harness.

`build.py` reads original source files, resolves their dependency closure, and
writes a transparent instrumented overlay under ignored build/. It changes the
Host backend and adds registration/host-write/submit hooks, preserving the real
plan, owner, loader and arithmetic. Read/write metadata is supplied at concrete
operation wrappers; unknown types and changed anchors fail closed. Compiler
-MMD manifests pin actual dependencies. No SYCL or accelerator loader is linked
into the executed host binaries.

## Gates and retained evidence

- Independent checker tests: 33/33, including missing edges, WAR readers,
  transitive cross-queue order, partial poison through two copies, lifetime,
  omitted bindings and randomized numerical mismatch detection.
- Actual-owner failure subprocess tests: 2/2, exit2 without executing pending
  closures for poisoned-index and missing-edge errors.
- Malformed/valid index guards: 46/46 under CPU ASan/UBSan/float-cast-overflow.
- Patched original integration suite: 13/13 in both parallel and serial core,
  each under seeds0,1,17,73. The original NumPy reference/test body is executed;
  only its packet-local memory-plan output destination is redirected.
- Shipped mini: both card counts, four seeds; full buffers/tokens agree across
  schedules, while snapshot poison is reported in every run.
- Real-weight short prompt: first two original prompt tokens, then one genuine
  generated-token input, two-card resident frozen parallel. Reports retain all
  96 captured layer hashes, token IDs, exact inputs, source/binary identity and
  sanitizer diagnostics. This shortened prompt is a safety gate, not a benchmark.
- Full original 87-token prompt: first generated token and all48 layer fixtures
  matched the saved arithmetic-v1 CPU oracle: 48/48 layer hashes and token332,
  with zero sanitizer violations. No native exactness or performance conclusion
  follows.
- Native syntax only: backend, adapter, ng native and serial Core, 4/4. No native
  executable was linked or run by those checks.

The final outcome and hashes are in build-receipt.json. Detailed numeric gates
are integration-gates.json, mini-shipped-gates.json, real-short-gates.json and
real-oracle-gate.json. Gzip JSONL traces retain every submission from the short
real executions, including initialization. The source-derived native position0
enumeration expands split GEMV phases; it is labeled separately from executed
CPU events. No unmeasured result is a performance claim.

## Reproduce on CPU

From repository root (the supplied real input/model files must already exist):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/build.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/build.py --patched
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/run_unit_tests.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/test-fatal-owner.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/run_gates.py all
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/mini_adversarial.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/enumerate_native.py
```

Runs require new scratch output paths; they do not overwrite existing evidence.
Compilers run at most two jobs. Real resident CPU runs allocate roughly53 GB
plus state; admit current host capacity before reproduction, without changing
memory/swap/cache settings. Scratch cleanup removes only packet19/build/scratch
and bytecode caches after receipt/trace retention. Binaries/reconstruction
sources stay in ignored build/; originals are never changed.

Optional syntax-only reproduction uses check_native_syntax.py under the same
nice/ionice/environment wrapper. It compiles headers/translation units only.
No script here grants device admission or overrides FAULT HALT.

## Limits

This is a declared-access submission checker, not machine-code address
instrumentation. Incorrect contracts can hide internal accesses. Contracts model
the valid active path; a kernel that returns early on error may not write every
claimed output. Poison/index negative tests and local device guards cover that
risk independently, but do not prove all internal failure-path stores.

CPU GEMV arithmetic fuses native split partial/reduction kernels; native internal
edges and workgroup barriers are source-audited/enumerated, not executed by this
scheduler. CPU exactness cannot test driver mapping, event-pool residency,
compiler translation, EnableDeferBacking effects or hardware fault behavior.
The conservative cross-card host fence patch is containment requiring device
qualification, not a proven cure. The smallest post-reboot event/copy smoke is
specified in ROOT-CAUSE.md, before any full model load.
