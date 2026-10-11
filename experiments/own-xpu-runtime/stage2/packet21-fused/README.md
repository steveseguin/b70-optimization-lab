# Packet 21: fused chained decode, arithmetic v2

CPU preparation for the quantized compressed Qwen3.8 Flash-Next UD-IQ3_XXS
model. This is a separate model identity from the FP8 lane. No device ran;
there is no measured speed claim. The host remains in FAULT HALT. This packet
does not edit packets 13–20, CURRENT.md or the scoreboards.

The source baseline is committed packet18-decode-v2, with packet20's fusion
prototypes and rule (ii) design. [source-provenance.json](source-provenance.json)
records the commit and original SHA256 values. The immutable arithmetic oracle
is [v2 incident retrospective](../../../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective).
The same executable accepts `--fusion on` or `--fusion off`; off preserves
packet18's native launch schedule and equations. Frozen and R5 remain separate
dispatch choices.

## What runs together

Sibling GEMVs concatenate their output-row ranges in one device-resident table.
Each row retains its matrix's dequantization, lane tree, split tree, and BF16
store. Split4's four partials and adjacent final tree execute within one group;
no partial is rounded earlier or accumulated in a different order. Rows inspect
at most eight ranges, then take one uniform matrix/variant switch. Each row
has 128 threads; nonsplit rows use one subgroup and leave three idle. Paired
gate/up rows execute their two dots in sequence, round each to BF16, then
perform the original activation and BF16 store. This costs extra registers,
local memory and idle lanes; the launch reduction is not a speed measurement.

Bundles cover HC low/inject, GDN qkv/z/a/b, QSA qgate/k/v/iq/ik, shared
router/gate/up/scalar, routed expert gate/up, and PLE key/value. HC input
activation and mixing are evaluated inside consuming GEMVs with the same BF16
boundaries. One designated row materializes diagnostic intermediate bytes;
sibling rows never depend on that write. Device rows recompute the input
transform into local storage. The CPU emulator evaluates the same pure
expression once per input within a submission. Nothing is reused between
submissions, tokens or requests. Attention output includes the HC residual,
with one output row owning each corresponding stream coordinate.

The route/rank launch uses four work-groups and stores selected IDs and
probabilities. Routed GEMVs index the single 2,560-wide input row; the old
repeated gathered input remains allocated and initialized for control-layout
compatibility, but is not copied or consumed. Probability normalization runs
in its own group inside the expert launch, whose other groups do not read it.

Non-GEMV producer/consumer chains retain original group bodies and reduction
trees, executing phases with barriers in one work-group. They cover GDN,
QSA, expert-status pairs, MoE final combination/residual, PLE, and initial
stream broadcast/norm. This deliberately conservative synchronization can
serialize work and is an open device-performance risk.

## Measured CPU submission census

Final measured counts are recorded in [launch-census-measured.json](launch-census-measured.json).
The census executes the real model with site logging and sums actual compute
submissions. It is not a planned count or a device timing measurement.
| Layer kind | Count | Frozen off | Frozen on | R5 off | R5 on |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary GDN, layer 0 | 1 | 49 | 17 | 44 | 17 |
| Other ordinary GDN layers | 33 | 49 | 18 | 44 | 18 |
| GDN + PLE, layer 1 | 1 | 59 | 21 | 53 | 21 |
| Upgraded GDN, layer 2 | 1 | 47 | 18 | 44 | 18 |
| QSA layers | 12 | 55 | 18 | 48 | 18 |
| Head/control | 1 | 13 | 10 | 12 | 10 |
| **Whole token** | | **2,445** | **876** | **2,181** | **876** |

Counts in layer rows are per layer. Layer 0’s first norm shares the initial
stream-broadcast submission, charged to head/control. These totals include
all 48 layers, both owner control paths and the final head. Every census arm
emitted the same token and all 48 identical layer fixtures. The full 64-token
frozen and eight-token R5 gates independently record 876 for every generated
row; their 86 preceding prompt positions each use 871 (the prediction head
runs only for generated-token rows). See [cpu-token-launches.json](cpu-token-launches.json).

There is no positive gap to the requested ceilings: frozen is 50 below 926;
R5 equals 876. Relative to packet20’s planned minimum, this implementation
retains 47 additional interlayer/final-norm boundaries, 144 status/ordered-mixture
submissions (three per layer), and one PLE-tail/norm boundary. Conversely, it
puts split partial/final trees inside one group, removing 242 frozen or 192 R5
submissions that packet20’s rule (ii) construction retained. Thus
`926 + 47 + 144 + 1 - 242 = 876` and
`876 + 47 + 144 + 1 - 192 = 876`. This reconciles different legal constructions;
the headline counts above come from actual CPU submissions, not this calculation.

| Dispatch | Projected issue cost, fusion off | Projected issue cost, fusion on |
| --- | ---: | ---: |
| Frozen | 73.35 ms/token | 26.28 ms/token |
| R5 | 65.43 ms/token | 26.28 ms/token |

These are **projections at 30 microseconds per launch, not measured token times**.
The measured descriptor tables occupy 59,584 bytes on logical owner 0 and
59,736 bytes on owner 1; the admission reserve remains one MiB per owner.

Timing categories follow submissions: a GEMV launch now includes its folded
prologue/epilogue work. Compare total device time and wall time directly; the
GEMV/non-GEMV split no longer assigns identical arithmetic to each category.

The reference to beat remains 28.49 tokens/second (about 35 ms/token). The
30 microsecond issue-cost projection is a multiplication of launch count by
prior evidence, not a prediction of achieved throughput. Device work, memory,
JIT, host waits and duplicated input transforms can dominate what remains.

## Deliberately unfused sites

| Site | Reason retained |
| --- | --- |
| `blk.*.hc.a.norm` (except layer 0), `blk.*.hc.f.norm`, `final.norm` | Global reductions need completed producer buffers. Keep the layer/snapshot boundary; a group barrier cannot synchronize a grid. |
| `blk.*.expsdown`, `blk.*.shexpdown` | Routed and shared down projections read different inputs. The shared projection is already one launch. |
| Ordered mixture inside `blk.*.moe` | Its separate launch preserves the expert accumulation tree and produces a complete buffer before the fused combine/residual consumer. |
| `blk.*.expsgate.check` + `expsup.check`, and `blk.*.expsdown.check` | The first pair is fused together but stays separate from GEMVs. Keep fail-closed status validation and sticky-error propagation before consumers; no new consumer-prologue fault proof is claimed. |
| `blk.1.ple.hash` and host PLE lookup | Keep index validation and the host lookup boundary. The PLE tail chain remains separate from HC norm. |
| `begin.0`, `begin.1`, `argmax`, `commit.0`, `commit.final` | Preserve admission, global argmax reduction and transaction/commit boundaries. |
| Snapshots, embedding lookup, streamed weight release, `handoff`, `handoff.result` | Preserve bytes, allocation lifetimes and mandatory host completion fences. Copies/lookups are not counted as compute kernels. No cross-card event is borrowed. |

Some norms are included where the entire dependent phase safely fits one
work-group (for example PLE); the table refers to remaining boundaries.
Shared down is already a single launch and has no sibling with the same input.

## Evidence and hardening

[build-receipt.json](build-receipt.json) binds source closure, host and device
binaries, precision flags, input manifests and CPU receipts. Precision flags
are asserted on every device compile command and every generated `link.txt`.
The recursive math gate rejects platform exp/log/pow/sin/cos in the device
source closure. Device binaries are compiled and inspected only.

The owner, native backend, shutdown ordering, cross-card fences, initialized
snapshots, index guards with safe substitutes, sticky errors, NEO refusal and
memory admission are preserved. Descriptor allocations are admitted and leased
through completion; one MiB per card is conservatively reserved in the window
memory census. Actual allocator counts are retained separately.

[review-identity.md](review-identity.md) and [review-alias.md](review-alias.md)
are independent reviews of arithmetic and read/write hazards. [FIXTURES.md](FIXTURES.md)
describes matrix classes and fixture limits. [cpu-tests.json](cpu-tests.json)
collects the final gate receipts; sanitizer evidence is retained separately.
[CPU preparation closeout](CLOSEOUT.md) and the [negative-result index](DO-NOT-REPEAT.md)
record what worked, what was rejected and the remaining gates.
No tolerance is accepted. Fresh processes under GNU and Intel host compilers
emit identical fixture byte files.

| CPU gate | Result |
| --- | --- |
| Fused frozen, two-card resident | 64/64 tokens and 384/384 layer fixtures equal v2 |
| Fused R5, two-card resident | 8/8 tokens and 384/384 layer fixtures equal v2 |
| Integration | 13/13 cases with each non-GEMV dispatch |
| Fusion off control | 13/13 cases; six direct packet18 comparisons equal |
| Deliberately incorrect fixtures | 2/2 rejected |
| GNU/Intel fixture repeats | Eight fresh processes agree: 553 GEMV output checks and 72 non-GEMV fixtures + six chains + eight controls + 16 actual-adapter checks per relevant process |
| Randomized mini dependency order | 16/16 runs: both card counts, both non-GEMV dispatches, four seeds; zero violations |
| Randomized integration dependency order | 104/104 cases over four seeds and both dispatches; zero violations |
| CPU guard sanitizers | 33 dependency-checker, 27 adapter-bound and 19 core-bound checks pass |
| Real-model randomized short case | Four seeds, two positions, 96/96 fixtures and both tokens equal packet18; zero violations |
| Full-prompt dependency execution | All 87 prompt positions, first token and 48/48 layer fixtures equal v2; zero violations |

The real-model randomized dependency gate is recorded in
[sanitizer-real-short.json](sanitizer-real-short.json) and
[sanitizer-real-full.json](sanitizer-real-full.json). Its short case starts at
position zero and feeds one generated token back in, across four dependency
orders on two resident owners. The full case reads the 87-position prompt and
checks its first token and 48 layer fixtures against v2. The checker sees
between-submission dependencies; intra-launch races are separately addressed
by the ownership/barrier reviews and remain subject to K1 on device.
The full chained run executed 92,949 submissions including copies, with
`max_ready=1`: its explicit dependency chain offers no alternative ready order.
The four-seed runs do not imply concurrent execution where the DAG forbids it.

## Sealed binary identities

| Ignored build artifact | SHA256 |
| --- | --- |
| `host/own-rt-iq3` | `a40227010dd934ab0fa8a07e3b9bd40cc9c46ab82c53b3044601015ddae02d7e` |
| `device/own-rt-iq3` | `b4189d16ba87fdd56879efb21aae65f7e2b69e0ecb4877f2b536a21ab6477698` |
| `device/fused-fixtures` | `9fe53ebb5da21f2fdcf68dfb7de3ad90e912f406c4b16e5a0162e5979aa463a6` |
| `device/nongemv-fixtures` | `aedff66aa54101ea913e0e0d2a3e7e86857559275d03c9748415f51d45f5dafa` |

These native artifacts were compiled and inspected only. Their device gates
remain pending. The complete artifact list is in the build receipt.

## Rebuild and next work

From the repository root, CPU preparation is:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet21-fused/build.py --phase all
```

It builds with at most two compiler jobs and uses two numeric threads. The
ignored build directory holds binaries and retained input fixtures. Temporary
CPU outputs can be removed after their hashes and comparisons are recorded;
sealed K1 inputs and compiled binaries must remain. [Retention notes](RETENTION.md)
explain the retained evidence and scratch cleanup. The original weight store
and v2 oracle are external/local inputs, not copied into this packet.

[WINDOW.md](WINDOW.md) contains exact, separate K1/W0/W1/W2/W3 commands;
[DEADLINES.md](DEADLINES.md) separates expected duration, submission budgets
and watchdogs. Every window refuses the sealed faulted boot. A reboot and
owner authorization are still required. No device window is launched here.

After device qualification, the next substantial lever is segmented replay,
following [packet20 REPLAY.md](../packet20-launch/REPLAY.md): stable dynamic
state, original active-prefix reduction trees, retained allocation ownership,
and explicit host fences between cards. Host embedding/PLE lookups and
snapshot boundaries must be resolved honestly; no cross-context graph or
single-submit claim is assumed.
