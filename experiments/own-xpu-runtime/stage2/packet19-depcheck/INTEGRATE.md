# Packet18 integration handoff

**Packet18 was not edited. No device ran. Native root cause remains unproven.**
Apply reviewed hunks to your current packet18 files, not wholesale copies of
packet16 over concurrent packet18 arithmetic changes.

## Exact hunks

- `0001-define-fixture-snapshot-bytes.patch`: main.cpp, Engine::initialize,
  per-card control initialization. Zero snapshots using bounded upload after
  slabs exist, BEFORE the missing-active skip. Full snapshot D2H includes
  unwritten layers on the other card, and unused first-layer/mini slices.
- `0002-guard-device-computed-indices.patch`: adapter.cpp,
  Bound::{failed,fail,safe_id,safe_position}, tiny, simple and Glue. Validate
  before float-to-int conversion; clamp address indices; use atomic sticky
  errors and uniform workgroup guards. Keep packet18's math functions.
  In packet15-nongemv/kernels.hpp, ng::group: guard selection ranks, score IDs,
  softmax list length, and every attention_value ID independently. Port these
  branches into whichever header packet18 actually uses. In packet4/core.hpp,
  Core::{safe_id,safe_position,run}, and kernels.hpp integrated::evaluate:
  also guard the serial control and uint32 position before narrowing. Existing
  native expert GEMVs already validate routes before forming weight addresses.
- `0003-contain-cross-card-native-event-waits.patch`: backend.hpp,
  Context::{dependencies,compute,copy,marker,forget,clear_events}. Track event
  queue ownership; host-wait foreign events with a bounded deadline and pass
  only same-card native wait-list entries. Keep owner.cpp's global chain.
  This is conservative containment, NOT a diagnosed causal repair. Added host
  fences invalidate old wait-count/performance claims.

Complete affected functions are under patched/. Source pins bind original and
patched bytes. All patches pass git apply --check against recorded packet16/15/4.
Do not apply them to protected originals during this task.

## CPU check on packet18

The builder reads a packet by path and writes only packet19/build. It substitutes
an instrumented host backend, captures concrete operation objects by value,
and retains the real Engine, plan, owner submission/lifetime logic, loader and
numeric operations. Its generated CPU owner replaces only hold_for_supervisor
with a report-and-exit path. Never port that CPU-only fatal helper into the
native owner: the real device retention policy remains unchanged.

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/build.py --source experiments/own-xpu-runtime/stage2/packet18-decode-v2 --tag packet18
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 DEPCHECK_SEED=17 DEPCHECK_REPORT=experiments/own-xpu-runtime/stage2/packet19-depcheck/build/packet18-mini.json experiments/own-xpu-runtime/stage2/packet19-depcheck/build/packet18/depcheck-runtime --mini --card 0 --cards 2 --memory resident --max-new 3 --output experiments/own-xpu-runtime/stage2/packet19-depcheck/build/packet18-mini
```

Use fresh output paths, seeds0,1,17,73 and both card counts; compare all buffers,
layer hashes and tokens. --tag packet18 keeps this build separate. --source uses the supplied packet,
while --patched selects the
packet16 overlay gate; it is not a magic port onto packet18.

Review rewrite anchors and generated sources first. If packet18 changes Host,
Engine::dev/allocate/upload/prepare_token, concrete operation types, binding
layouts or geometry, adapt build.py and instrument18.hpp explicitly. Unknown
operations fail compilation; missing rewrite anchors must fail build. Include
unused bindings in ownership validation and describe partial writes precisely.

run_gates.py executes packet16's original 13-case test body, redirecting its only
packet-local output write, and real short/full prompt gates. Packet18 must bind
its own oracle wherever its arithmetic differs. Keep complete dependency/source
hash manifests and exact commands with each result.

The host mock still fuses native split GEMV phases. Source-derived native
submission enumeration is provided, but native kernels/driver event storage are
not executed by the CPU scheduler. A clean result cannot replace the tiny
post-reboot event/peer-copy smoke in ROOT-CAUSE.md.

## Checked packet18 snapshot

The current source was read without editing it. Eight CPU mini runs (both card
counts, core/parallel, seeds0/17) passed numeric schedule repeat comparison;
its unchanged snapshot-read defect was detected. See packet18-adapter-gate.json
for exact source hashes. This is not a v2 oracle or device qualification.

Concrete differences already supported in instrument18.hpp/build.py:

- packet18 `kernels.hpp` ng Args has19 slots: sticky error15, RoPE table16,
  position17, active18. The old contiguous12-byte control contract is WRONG here.
- packet18 Bound has RoPE at tail+4 and Glue appends an unused control afterward.
  The table is a read for QSA prepare/pool; ownership applies to all bindings.
- packet18 removed ng entry/exit bridge submissions. Keep that change; do not
  restore bridges while applying packet16 guards.
- packet4 Core/evaluate hunks map to packet18 `core_v2.hpp` and
  `runtime_kernels.hpp`. Build packet18 `runtime_kernels.cpp`, not packet4's
  implementation. Keep deterministic-math and table-based RoPE arithmetic.
- The builder stages the hash-checked rope.bf16 asset under its own build path
  because the runtime finds it relative to __FILE__. It never regenerates the
  table or edits packet18's copy.

If those layouts change, update the separate18 contract and rerun its mini gate.
