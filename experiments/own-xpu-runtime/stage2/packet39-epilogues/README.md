# Packet 39: exact row epilogues, prepared on CPU

Seven of twelve compiled format/shape cases pass the offline assembly gate.
They could remove **431 launches per token**. No device program or discovery ran,
no speed was measured, and no runtime default changed. K0 and G4 are prepared
for the coordinator. The lane remains open; this packet closes CPU preparation.

The model is the separately scoped Unsloth IQ3_XXS quantized compressed version
of Qwen3.8 Flash-Next, using the lab's arithmetic identity v2. The controls come
from the measured packet29 launch plan, packet28 paired/rows4 GEMVs and packet33
selected down/segment bodies. This does not make a claim about the FP8 lane.

## Chains and arithmetic

[CHAINS.md](CHAINS.md) records each tiny launch, its producers, consumers,
reductions and rounding points. [baseline-geometry.json](baseline-geometry.json)
pins the actual measured dispatch. Independent reviews checked both the plan
and the unfused/fused sources: [chain review](chain-table-review.md),
[arithmetic review](identity-review.md), and [harness review](review-identity-harness.md).

| Implemented chain | Why the row epilogue can preserve identity | Offline outcome | Launches removed/token if selected |
| --- | --- | --- | ---: |
| Paired expert gate/up + both checks + activation, IQ2_S/IQ3_S | Round both projections to BF16 and widen before the unchanged SiLU/product; vote over all routes before activation writes | Rejected: added predicate spills in both formats | 0 |
| Paired expert gate/up + both checks only | Keep raw outputs/statuses; invalid slot's row zero atomically sets sticky 0 to 1; activation remains separate | IQ2_S admitted; IQ3_S rejected for one extra GEMV-loop instruction | 94 |
| Expert down + status | p33.down.select body unchanged; status/sticky update requires no expert reduction | Admitted | 48 |
| HC low + activation | Measured p28.dense.rows4 split-four tree, BF16 projection, widen, divide by four, SiLU, BF16 activation | Admitted | 97 |
| Shared up + activation, Q6_K/Q8_0 | Existing shared gate is available; preserve gate BF16, up BF16 and activation order; keep measured p28.dense.rows4 body | Both admitted | 48 |
| Attention output projection + residual combine | Projection finishes with the original split-four tree and BF16 round; four independent stream rows retain their operation order | Admitted | 48 |
| Shared down + shared blend + FFN residual combine | Move existing expert mixture and scalar shared gate before shared down; retain mixture BF16, `0 + mixture * 1`, shared contribution BF16 and blend BF16 before residual combine | Admitted | 96 |
| GDN QKV + four-tap channel convolution/history update, Q6_K/Q8_0 | Round QKV to BF16; ordered four-tap FP32 sum uses old history before shifting; SiLU precedes output BF16 | Both rejected: one extra scheduling instruction inside the GEMV loop | 0 |

Raw GEMV outputs remain available for the packet29 trace reader and G4 byte
comparisons. Several have no remaining computational consumer after fusion;
they are retained for those observable diagnostics, not a claimed data dependency.
Status arrays and sticky error remain observable. Atomic compare/exchange only
changes sticky zero to one and cannot erase an existing nonzero error.

HC gate-to-mix consumes four gate rows. Routed expert down-to-mixture consumes
ten experts. GDN z-to-gated includes a 128-value head reduction. Norms, routing,
argmax and QSA preparation also require reductions. Those stay parallel and
unfused. Splitting a GDN reduction then delaying z adds a launch before removing
one and offers no launch reduction. PLE convolution-to-add is a valid non-GEMV
tail worth only one launch per token and is left outside this GEMV packet.
No serial whole-vector reduction, extra barrier or extra local array was added.
Rows4 retains the incumbent local array/barrier; attention retains its finish.

## Assembly and launch budget

[Assembly pairs](assembly-table.md) gives all twelve controls/candidates;
[assembly-review.json](assembly-review.json) carries loop counts, SIMD widths,
payloads, spill metadata and final ELF-text identity. There are 32 final offline
kernels including controls, original runtime tails and compiler wrappers.
[Independent assembly review](review-assembly.md) covers the admitted bodies.
The five rejected cases remain reproducible evidence and are excluded from
G4's final dispatch recommendation even if their timing happens to win.

Every admitted case keeps SIMD width, GEMV-loop cost and spill status under the
static gate. Instruction/message deltas are static full-program differences,
including exceptional branches. They are not executed-path counts or measured
cost per row. In the attention finish, SIMD32 covers up to 32 independent rows;
JSON gives that amortization separately. [Runtime compilation limits](runtime-options.md)
explain why future driver JIT output still needs its own gate.

The 431 removable tiny launches account for an estimated **2.277 ms/token** of
the old measurements. This is a launch-removal budget, **not a predicted net
speedup**: added epilogue work is unmeasured. The estimate uses packet29's
63-token class totals; IQ2 checks are prorated by 47/48 layers, and the two `moe`
launches have no separate receipts, so half of that aggregate is explicitly
allocated to the shared blend. [launch-estimates.json](launch-estimates.json)
retains those assumptions and the rejected full proposal's 517-launch budget.

## Identity and prepared timing gates

[CPU receipts](cpu-gates.json): GCC and icpx, two fresh processes each,
1,440 fixtures, **10,400 finite/control observable comparisons passed**,
and **7,200 hostile admission rejections passed**. Fixtures cover every family,
odd row counts, BF16 ties, invalid/partial routes, inactive/sticky controls,
invalid context positions and poisoned nonfinite inputs. Compile and link use
precise arithmetic flags. [Math grep](math-gate.json) checks the 31-file local
include closure for forbidden platform nonlinear calls.

The 2,592 nonfinite comparisons have **36 GCC NaN-payload mismatches** in full
expert activation/shared activation; icpx has none. These are diagnostic under
packet29's finite-only GEMV policy. They are recorded as failures, never NaN
"equality": `passed=false`, `nonfinite_qualified=false`, with a separate passing
finite/control gate. This packet does not claim arbitrary nonfinite exactness.
G4 still requires exact bytes for its NaN fixture and will fail if they differ.

The actual packet29 host plan overlay passed **8/8 generated tokens and
384/384 layer-byte comparisons** against the v2 incident oracle in 2,040.5
seconds, with peak child RSS 1,236,636 KiB. Its final result is in
[real-eight.json](real-eight.json). This uses the host
GEMV backend with seven substituted scalar epilogues, not the device lane bodies.
The source/helper/object pins distinguish that CPU evidence from native proof.
[CPU identity details](cpu-identity.md) explain the gate's scope.

[Wrapper tests](protocol-tests.json): twelve CPU mock groups passed, including
JSON persistence, unchanged `LD_LIBRARY_PATH`, missing libraries, cursor-relative
fault latches, graceful failure and dispatch rejection/conflict handling.
G4 is prepared for **84 device byte checks**, then **200 repetitions per arm per
class**, using eight independent full-size banks above 8 MB and event sums for
all launches in each chain. It has not run. One G4 window is screening only;
a fresh repeat and native full-model oracle are still required for a verdict.

## Coordinator and restoration

Use the exact K0 then G4 commands in [WINDOW.md](WINDOW.md). They accept `--card N`.
K0 and G4 are byte-identical native executables; K0 selects compile smoke inside
the binary, guaranteeing it builds the actual G4 device images. [BINARY-HASHES.md](BINARY-HASHES.md)
and [build-receipt.json](build-receipt.json) bind binaries, sources and evidence.
The wrapper forwards the coordinator's full environment, checks libraries by
normal loader resolution, and refuses stale/mismatched K0 receipts.

[INTEGRATE.md](INTEGRATE.md) identifies new packet26-style dispatch keys, launch
sites that disappear and necessary ordering. Nothing here edits the runtime's
closed dispatch registry. [DEADLINES.md](DEADLINES.md) records reported duration
and generous watchdogs; failures are written before graceful teardown, with
no retry or hard kill. [CLOSEOUT.md](CLOSEOUT.md) and [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md)
retain rejected arms and conditions for reconsideration.

The 2.1 MiB [offline archive](evidence/final-offline.tar.gz) is intentionally
tracked: disassembly, GEN bytes, final ELF text/metadata and exact embedded
SPIR-V cannot be reconstructed from count summaries alone. Its consumer is
`analyze.py`/`assembly_gate.py`; [offline-retention.json](offline-retention.json)
records every member's verified hash and restore paths. Restore only within this
packet. Earlier iteration summaries and patches remain under `evidence/`.
Ignored `build/` retains coordinator binaries and reproducible compiler outputs;
transient compilation and mock scratch is removed before handoff. Source packets
and other jobs' files remain unchanged.
