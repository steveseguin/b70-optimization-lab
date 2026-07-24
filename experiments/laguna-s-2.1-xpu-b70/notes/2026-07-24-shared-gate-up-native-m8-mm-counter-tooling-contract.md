# Laguna separate shared gate+up native-M8 MM cold-counter tooling contract

Date registered: 2026-07-24 America/Toronto

Status: this note resolves the counter-tooling contract after the sealed
four-card component pass. It authorizes construction, CPU-only testing, source
freezing, and independent audit of a fresh cold-counter toolchain only. It
does **not** authorize a counter capture, XPU command, model generation,
endpoint/service work, payload creation, network access, record claim, reboot,
or LocalMaxxing submission. Counter execution requires a later packet-only
authorization child that freezes the resulting toolchain and all execution
identity.

## Authority and frozen identity

This contract supplements, without weakening, the original preregistration
and its reaffirmations:

1. `2026-07-23-shared-gate-up-native-m8-mm-preregistration.md`;
2. `2026-07-23-shared-gate-up-post-incident-reaffirmation.md`;
3. `2026-07-23-shared-gate-up-runtime-guard-fix-and-reaffirmation.md`; and
4. `2026-07-24-shared-gate-up-native-m8-mm-component-pass.md`.

The component pass is the required predecessor and remains the exact evidence
anchor: vLLM `503f7784cf9d1704109b1e4650427fb4f417d604`, XPU kernels
`c59aaadbbfd350c2b5f4ad663e247c2811ae3181`, component tools
`4cef996c94502ad06233caa55d5be019d13a5114`, and packet-only authorization
`f04d7431224017859ef892b1251f2a87fc1dee4a`.

All live fixture, cache, temporary, log, run, and evidence paths must be under
the internal local-NVMe/ext4 `/mnt/fast-ai` roots. The external Corsair USB is
backup-only and is not an admissible live input or output.

## Frozen treatment and exactness boundary

The sole counter comparison is the already-passing separate ordered shared
gate+up treatment:

| Arm | Gate | Up |
|---|---|---|
| Control (`A1`, `A2`) | stride-zero `B=8, M=1, K=3072, N=256` BF16 BMM | stride-zero `B=8, M=1, K=3072, N=256` BF16 BMM |
| Candidate (`B1`, `B2`) | native `M=8, K=3072, N=256` BF16 MM | native `M=8, K=3072, N=256` BF16 MM |

Both projections remain separate and execute strictly gate then up. The
candidate selector is `VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=1`; the standalone
gate and shared-down selectors are literal `0`. Merged N=512, logical B=16,
concatenation, packing, custom fusion, reordering, overlap, and shared-down MM
remain forbidden. All other frozen record-stack behavior remains incumbent:
BF16 rounding boundaries, shared SiLU/multiply, shared down, routed work,
fixed-rank reduction, attention, KV writes, collectives, DFlash, sampling,
and eager graph-off execution.

Every captured gate/up output pair must be raw-bit exact between control and
candidate, separately for gate and up and for all 13 repeats. The counter
campaign also binds and re-verifies the sealed component final manifest whose
raw-BF16 and `torch.equal` proof covers gate, gate repeat, up, up repeat, gate
SiLU, actual BF16 multiply, shared down, shared+routed add, and fixed-rank
reduction. The direct counter fixture deliberately profiles only the two
ordered projections; it must not add downstream kernels to the selected
scope. Candidate execution must prove exactly two marked native MMs in
gate-then-up order, while incumbent and unmarked paths retain BMM. Any
mismatch, nondeterministic repeat, dispatch/order failure, runtime-stack
drift, selector ambiguity, fixture/output mutation, missing hash, or
evidence-closure failure is fail-closed.

## Frozen cold-counter protocol

The campaign covers physical cards 0, 1, 2, and 3 sequentially. Each card uses
fresh private processes and private local-NVMe output, `HOME`, cache, and
temporary trees for every arm. Its arm order is fixed and may not be
randomized, omitted, reordered, replaced, or extended:

```text
A1 control -> B1 candidate -> B2 candidate -> A2 control
```

Each arm performs exactly 13 selected, completion-bounded ordered gate+up
pairs. A 128 MiB eviction touch occurs before every pair. Completion is
required before and after every selected pair. Pair indices 0 and 1 are
discarded; indices 2 through 12 are retained, yielding exactly 11 analyzed
pairs per arm. No warm-up, retry, replacement, extra arm, extra selected pair,
or favorable-subset selection is permitted.

The counter invocation must use `unitrace` device timing and metric query with
the `ComputeBasic` group and `gemm_kernel` selector. The separate packet-only
authorization must freeze the complete `unitrace` command template, binary and
source hashes, selected-device binding, timeout/process handling, fixture,
runner, analyzer, runtime/source/model/device identities, and all expected raw
evidence headers and files.

Each physical-device preflight must retain both the parsed discovery record
and the exact raw `xpu-smi discovery -j` transcript. The analyzer recomputes
the transcript SHA-256 and parses it again before accepting the UUID, PCI BDF,
DRM node, device name, filtered visibility, or four-card mapping. A stored
digest that is merely syntactically valid is not evidence.

The repaired timing parser contract is an exact six-row timing-summary
multiset per arm: selected gate+up GEMM activity totaling 26 selected
`gemm_kernel` calls, plus the five expected fixture memory-copy summary rows.
Timing-summary row order is not evidence because `unitrace` may sort by
measured time; names/call counts and the complete expected six-row multiset
must close exactly, with no missing or extra row. The selected GEMM timing and
properties must link to the same Level Zero total and exact expected headers.
Metric-query rows must have one exact verbose SIMD16 kernel identity within
each treatment, 26 strictly ordered unique global query IDs, consecutive
gate/up IDs within each pair, and exactly the one eviction-dispatch gap
between adjacent pairs. Any different dispatch shape fails closed rather than
being reinterpreted.

The frozen CPU suite covers the authorization gate, runner, fixture, parser,
and analyzer. Every test source is itself part of the mandatory hash closure.
The suite exercises command-template normalization, one-shot action bounds,
PID-suffixed profiler-file closure, exact fixture call structure, the complete
ComputeBasic schema, matched-pair no-rescue rules, metric guardrails, runtime
exclusion inventory, and error-seal path confinement.

Pre-freeze CPU verification completed with 56/56 tests passing, Ruff clean,
AST parsing clean, `git diff --check` clean, and no bytecode cache left in the
tool tree. The suite includes a full synthetic four-card, sixteen-arm evidence
tree that exercises capture validation, analysis, finalization, terminal-only
crash resumption, final inventory, and final re-verification using real
parser-compatible timing and ComputeBasic CSV bytes.

Independent source-only audits caught and closed three execution blockers
before any device action: invalid dictionary subset checks that would reject
every arm, a failed-first-arm accounting path that could falsely claim no
profiler execution, and an unguarded root-creation transition. The frozen
runner now latches profiler start immediately after process creation, carries
that state through arm and campaign failures, and seals failures on either
side of the root/intent transition.

## Frozen acceptance requirements

All of the following are required. A global mean or aggregate can never rescue
a failed matched pair, failed card, or failed guardrail.

- Raw-exact outputs and all exactness/integrity checks pass for all 16 arms.
- On every card, both matched GPU-time comparisons win: `B1 < A1` and
  `B2 < A2`.
- On every card, the candidate aggregate GPU time across retained selected
  pairs is lower than control.
- On every card, candidate guardrails satisfy all of:
  - GPU-memory-read regression no greater than 2%;
  - LSC-read regression no greater than 2%;
  - thread-occupancy decrease no greater than 0.5 percentage points;
  - XVE-active decrease no greater than 0.5 percentage points; and
  - XVE-stall increase no greater than 0.5 percentage points.
- On every card, validity, split, overrun, lost, inconsistent, spill, SLM,
  partial-write, and LSC-write failure proxies remain zero.
- Across all four cards, the candidate global aggregate GPU time is lower than
  control. This is required evidence but is GPU-time-only and cannot override
  any preceding per-pair, per-card, or guardrail failure.

The later execution packet must define the exact arithmetic for retained-pair
and global aggregates before capture and must reject a type/unit/header or
metric-field mismatch rather than infer a substitute metric.

## Stop rules and authorization boundary

Any failed preflight, tool/hash/identity seal, physical-card mapping, private
path check, profiler arm, exactness check, six-row timing multiset, metric
parse, evidence closure, matched pair, per-card aggregate, guardrail, or
global aggregate yields `counter-failed-stop-before-endpoint`. The first valid
counter campaign is terminal: no rerun, additional sample, retry after a
parser/profiler failure, arm replacement, or sample selection is permitted.
The runner writes a packet-bound campaign-intent seal immediately after
creating the one-shot root. If that root is ever observed again, the runner
must not invoke device tooling or reuse it. An already terminal root is left
untouched; an unterminated partial root receives an abandonment seal, records
counter execution as unknown when an intent existed, and stops.
If an analyzer fails after a sealed capture, the capture remains immutable; a
separate authorization may permit only offline analysis of its sealed bytes,
never counter reexecution.

Analyzer and finalizer error writers may operate only after the authorization
packet has validated and only inside its exact direct `runs/` child. A
noncanonical or partial analysis, terminal, or final-manifest file is retained
and described by an immutable failure seal; it is never replaced. A complete,
valid analysis or final seal is not poisoned by an accidental repeated phase
invocation.

A passing counter campaign authorizes only construction and independent audit
of a separate cold endpoint preregistration. Endpoint execution, model
generation, payload creation, networking, record claims, and LocalMaxxing
submission remain unauthorized until later separately frozen gates pass.
