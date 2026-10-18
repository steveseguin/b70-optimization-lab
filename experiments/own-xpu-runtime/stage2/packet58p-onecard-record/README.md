# Packet58p: one-card tile16-only chain, prepared on CPU

**No device launch.** This copies packet58m's seven-window chain and packet58n's
exact down-tile16 selection. Route remains route-exp32-rank4, recurrence
rows4-shared, HC production. The two device binaries are byte-identical
copies from 58n; three CPU binaries come from 58m. Nothing was compiled.
The build is **72,734,584 bytes**, below 150 MB.

Readiness refuses until all three original 58n receipts are complete, every arm
is **12/12 exact at 128 tokens**, and tile16-only beats **each** production arm
by at least **0.5%**. It also retains matched miss paths, one boot, nine fresh
owners, at most 3% control drift and a candidate above the saved
24.338653323339745 tok/s record. The checker recomputes native outputs against
packet49. A saved ready flag cannot authorize launch. The reader executes
local frozen source snapshots; parent results are read at verification time
and never pinned into this packet's build seal.

The chain is K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps.
It preserves iq3-p49-split32-v1, twelve fixed prompts, 128 tokens, full BF16 KV
at context 4096, target-only greedy decode and the 18 GB immutable expert cache.
Fresh K1s choose zero-copy or streamed misses. All windows reserve the whole
host; **the coordinator pauses and drains lane B before launching and keeps it
paused through the gaps**. Only WS128 is timed. WS128x remains exactness-only.
A second timing run is still required for a speed verdict; the strict 512-token
gate remains false. No submission is performed here.

## CPU evidence

- [118 Python tests](evidence/python-cpu-gates.json): admission, oracle/reset,
  submission/API projection, synthetic winner/loser, refusal without retry,
  exact selection keys, finite-limit refusal and both copied drain repairs.
- [Twelve full argument paths](evidence/argument-gate.json): real queue argv →
  window entry → suite-driver entry → intercepted native exec. Both miss paths
  run for all five model windows. Operational receipts, live resources and
  leases are synthetic; selection, oracle, input tables, memory validation,
  masks and argv assembly are real. An audit hook denies device/model opens,
  execution and writes outside scratch.
- [Ten parser/oracle checks](evidence/startup-cpu.json) and
  [ten full-size startup/submit checks](evidence/fullshape-submit-cpu.json):
  3,446 allocation rows, 1,486 sites and contexts 32/4096. The CPU mock's sparse
  virtual arenas exceed 8 GB; physical RSS stays bounded. The priority probe
  exits before loading weights.
- [48 K1 byte checks](k1-cpu.json), both layouts;
  [postload check](evidence/postload-allocation-cpu.json).
  [Inherited compiler byte proof](evidence/inherited-byte-gates.json) is labeled
  inherited, not a new device run.
- [Seven host/VRAM budgets](evidence/budget-cpu.json) exactly match 58g.
  WS128 needs 118,308,908,048 bytes available: a 109,718,973,456-byte host
  bound plus 8 GiB reserve. No live host admission is claimed.
- [Drain scanner](evidence/drain-fix.json): two fixed copies, none unfixed.
  The clock-crossing negative control reproduces the old error in memory.
- [58g parser replay](evidence/submission-58g-dry-run.json): exact saved
  24.338653323339745 tok/s, specNumTokens omitted, no eligible new result.
- [Synthetic readiness](evidence/readiness-rule-cpu.json): exactly 0.5% passes;
  0.496% fails, as do missing arms, inexact outputs and a loss to either control.

exec_limits.py snapshots getrlimit before runtime imports and checks it
immediately before queue/window/native subprocess calls. Finite address-space
limits or any limit drift refuse launch. CPU-only CLI caps never run on import.
The small argument probe inherits unlimited AS to test this boundary honestly;
its actual child RSS is recorded and must stay below 8 GiB.

## Coordinator handoff

The exact 58g-style systemd command is in [ready.json](ready.json) and
[WINDOW.md](WINDOW.md). It is emitted only, never run by this preparation.
From the repository root, check the seals and readiness:

```bash
P=experiments/own-xpu-runtime/stage2/packet58p-onecard-record
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/verify_ready.py" --output "$P/ready.json" < /dev/null
```

After readiness passes, the coordinator alone supplies a fresh capture with
fault_review.py --output "$P/evidence/fault-review-58p.json". This was not run
during preparation. The queue validates its boot against the screen and derives
the newest-kernel-line-minus-two-seconds boundary. evidence/card0-58p-a must
remain absent until that launch. There is no retry or automatic launch.

## Reproduce CPU preparation and retain evidence

Use nice19, cores 8–15/24–31, python3 -B and stdin /dev/null for each script.
Run restore_build.py, postload_allocation_gate.py, fullshape_submit_gate.py,
startup_gate.py, k1_cpu_gate.py, budget_gate.py, argument_gate.py,
run_cpu_gates.py, and drain_cpu_gate.py. Rehearse the historical parser:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/packet58_submission.py" --dry-run-existing-result experiments/own-xpu-runtime/stage2/packet58s-onecard-submission/submission/card0-58g-a-v3/result.json < /dev/null > "$P/evidence/submission-58g-dry-run.json"
```

Finish code before seal.py, then run seal.py --verify, plan_gate.py and
verify_ready.py. Never edit/reseal after chain output exists. Submission pins
bind finalized tools to the build seal in one direction. The live record
threshold stays outside that seal.

build/ is ignored. [Restoration](restore_build.py) copies hash-matched binaries.
[Provenance](copy-manifest.json) and compiler receipts retain source identity.
Frozen parents remain needed for source closure and native RoPE constants;
this is a research packet, not a standalone public recipe. Stop preparation
if root free space falls below 25 GB. The passive plan retains the chain's
2,952,790,016-byte write allowance and 8 GB runtime disk floor.
No tracked artifact reaches 1 MiB.

[Closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet58p.md).
