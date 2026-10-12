# Complementary tiny geometry candidates

Prepared only; no device run. These entries complete the tiny-class study
alongside `tiny_*`. They retain the original arithmetic, types, rounding and
adjacent reduction trees. `extras_core.hpp` provides CPU arithmetic and
`extras_native.hpp` provides the runtime submission entries.

- Norm and combine/norm retain the two `specialised::body` stages, including
  the fixed width2560/heads4 specialization. Candidate geometries are plain
  range, WG32 and WG256 with all lanes assigned consecutive work items.
- QSA select retains `round2::group` stages0/1, local storage and barriers. It
  changes work-group width from32 to256 while each original tree node is still
  executed once at the same tree level. No sum is regrouped. The128-capacity
  fixtures are gate-only. The measured-shape fixture derives capacity256 from
  the existing128 fixture by repeating its retained pool bytes and setting
  position255. The CPU reference is recomputed for that exact input.
- Streams/broadcast, HC combine and PLE add keep the adapter’s per-element
  expression. Inputs and controls use a small concrete argument structure.
  The entry accepts the runtime Spec/bindings ABI, including scheduled
  active/error inputs. Range, WG32 and WG256 are compared against the actual
  packet18 adapter entry with implementation1.
- Status checks with1..32 entries retain the same adjacent FP32 sum of
  nonzero predicates, including each odd-tail +0 addition. One work-item
  evaluates that bounded tree privately. This removes the incumbent’s local
  accessor and barriers without changing operations. The prototype refuses
  longer lists. Commit and begin retain their scalar control operation and
  active/sticky-error order in one work-item. WG32/256 variants intentionally
  leave other lanes idle, allowing T1’s scalar launch result to be tested on
  these actual runtime bodies.

Every native capture is statically guarded at1024 bytes. The drop-in flat API
is `p42extras::flat_submit<WG>(Device&, Spec const&, Kind, bindings, deps)`; `WG=0`
means range. `p42extras::submit<WG>` accepts the existing ng shape/bindings and
scratch ABI for norm, combine/norm and select, with optional dependencies
forwarded to the first stage. Both paths validate extents,
memory/alignment and conflicting write/control/scratch aliases before launch.

The coordinator program is `build/extras/p42-extras`, with the common
`--card N --output DIR --repetitions 200 --authorized-device-window` arguments.
Add `--compile-smoke` for K0. Native measurements compare the unchanged runtime
entry with each candidate, 200 times each in alternating order. Host wall and
summed GPU event times are kept separately. Upload, reset and equality checks
are outside the timed region. Timing fixtures are explicitly selected at width2560/heads4/flags8 for norm
and capacity256 for select. Combine/norm fixtures use BF16 unit-offset gains
and are gate-only, with no deployed class alias; remaining cases are also
labeled gate-only. None of these
one-token payloads exceeds8MB. Outputs are compared byte-for-byte before and
after timing, and failing candidates become rows rather than ending the rest
of the study. Infrastructure and receipt-storage failures fail the window.

Runtime class aliases are separate from stable algorithm IDs. For example,
`p42.extras.check.range` applies to expsgate.check/expsup.check/expsdown.check;
commit and begin each map to both runtime sites. Norm maps to hc.a.norm,
hc.f.norm and final.norm: packet3/step/plan.hpp hc() calls norm with four
rows, including its final invocation, and norm() defaults unit=0. Combine maps to attn.combine and ffn.combine. The
wrapper must only emit dispatch rows for the exact measured shape and passed
associated gates. A cheaper geometry cannot be declared until T1 and K2 run.

CPU gates and binary/assembly hashes are recorded in `extras-cpu-gates.json`,
`extras-build-receipt.json`, and `extras-codegen.json`. Assembly is compressed
under `extras-evidence/`; whole-kernel instruction counts are static evidence,
not timings or fitted performance predictions.

CPU gates passed in four fresh processes (two GCC, two Intel strict): each
19 reference checks, 76 fixture geometry comparisons, 675 flat geometry
comparisons, 610 incumbent/Core comparisons across compact and exact scheduled
bindings, and 240 in-place geometry comparisons.
The fixture hash agrees across all four processes (`2622928ceb5d9e62`).

The offline compiler accepted two unique embedded SPIR-V modules and selected
62 final GEN kernels, including SYCL range wrappers. Direct named entry counts
are below; messages use the packet33 parser and exclude atomic opcodes (those
are separately counted in JSON). These are whole-kernel static counts, not
dynamic timing predictions.

| Kernel | Range instructions/messages | WG32 instructions/messages | WG256 instructions/messages |
|---|---:|---:|---:|
| streams | 279/14 | 300/14 | 300/14 |
| combine | 744/24 | 753/24 | 753/24 |
| ple.add | 279/24 | 286/24 | 286/24 |
| check | 234/13 | 236/13 | 236/13 |
| commit | 40/6 | 42/6 | 42/6 |
| begin | 39/5 | 55/5 | 55/5 |
| norm stage0 | 707/39 | 724/39 | 724/39 |
| norm stage1 | 331/33 | 352/33 | 352/33 |
| combine_norm (diagnostic) stage0 | 7802/55 | 7963/141 | 7963/141 |
| combine_norm (diagnostic) stage1 | 808/36 | 827/36 | 827/36 |
| select stage0 | not submitted | 1473/267 | 1155/223 |
| select stage1 | not submitted | 379/25 | 379/25 |

The archived unchanged baseline has norm stages415/39 and317/32 and select
stages1519/271 and381/25 (instructions/messages). WG256 select stage0 reduces
the direct WG32 entry from1473/267 to1155/223 while keeping114 barrier-related
instructions; stage1 remains379/25 and6 barrier-related instructions. No
barriers or SLM appear in the flat or norm candidates. The original generic
Glue kernel used for check/commit/begin declares a32768-byte local accessor;
its huge whole-kernel counts include unrelated operations, so they are not a
valid per-check cost comparison. The candidate replaces that shared body with
a compile-time operation and no local allocation.

The range streams/combine/PLE entries have279/14,744/24,279/24 static counts,
versus453/32,930/44,466/43 in the unchanged adapter SimpleNew entries. Norm
WG forms add instructions and do not reduce messages in this compilation.
Combine/norm stage0 WG forms spill4096 bytes per thread in the offline metadata
(compared with no private allocation in this candidate’s range entry); this
is evidence against these diagnostic variants, not a measured slowdown.
All conclusions about cheaper launches remain pending T1/K2.

Scheduled flat bindings match the deployed plan exactly: check inputs are
status/error/active and output is error; commit inputs are error/active/position
and output is position; begin inputs are active/position and output is error.
Streams, combine and PLE append active/error to their payload inputs. The
coordinator submits those signatures through both incumbent and candidate.
Combine and PLE bind output to input0 in place, as the plan does. The validator
permits only that equal-size/equal-type payload alias and the documented
scalar control aliases. Upload skips the duplicate output binding.
`extras_incumbent.hpp` is an exact CPU-only extraction of Bound/simple/subtree/
simple_body from the unchanged adapter, with its source hash. It strengthens
the gates by checking the actual incumbent body as well as Core.

The extras window prepares70 cases:23 cases have200 GPU/host measurements per
arm;47 are identity-only diagnostics. No device execution occurred here.
