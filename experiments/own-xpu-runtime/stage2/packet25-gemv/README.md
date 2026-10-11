# Packet 25: exact large GEMV candidates

CPU preparation only for `iq3-p17-detmath-v2`, with the frozen
`r234-sg32-split4-bf16` trees. **No device executable ran. No speed is claimed.**
This packet does not change packet 23, packet 24, the scoreboard, or the live
runtime. All device and real-model gates remain pending.

The [timing plan](timing-plan.json) binds the supplied 63-token class trace.
It supplies launch-group frequencies and deadline sizing, not measurements of
these candidates. Source arithmetic is [arithmetic.hpp](arithmetic.hpp), using
unchanged packets 7–10. [frozen-gemv.txt](frozen-gemv.txt) preserves the tracked
packet-23 control source at preparation; mutable sibling work is not a build
input. We retain the control's WG128, SG32, one-row geometry. Dense Q6/Q8 qkv,
z, qgate and logits use SG32; k/v and attention output use the frozen split4.
The QSA output is Q6, 2560 × 6144, as the tensor census confirms.

## Candidates and bit identity

All listed candidates pass the registered CPU gates on GCC and icpx, with
fresh processes and matching output digests. See [cpu-tests.json](cpu-tests.json).
A CPU pass is not a device pass. See [WINDOW.md](WINDOW.md) for the remaining gates.

| Class / formats | Candidates beyond current | Exactness argument |
| --- | --- | --- |
| Routed gate/up, IQ2_S and upgraded IQ3_S; supplemental IQ3_XXS fixtures | `rows4`, `wg32`, `private_decode`, `paired_input`, `half_table`, `staged` | Each row/peer keeps its 32 original lanes, increasing tile and j order, adjacent tree, and separate BF16 cast. |
| Routed down, IQ4_NL | `rows4`, `wg32`, `private_decode`, `wide8`, `staged` | Same octets, nibble/level mapping, scale multiplication and row tree. Route slots are never sorted or merged. |
| GDN qkv, Q6 and upgraded Q8 | `rows4`, `scale8`, `wide8` | Same Q6/Q8 FP32 scale and signed code, then weight × input and serial add. |
| GDN z, Q6 and upgraded Q8 | `rows4`, `scale8`, `wide8` | Same as qkv, independently qualified. |
| QSA qgate, Q6 | `rows4`, `scale8`, `wide8` | Same SG32 tree and BF16 boundary. |
| Attention output and QSA k/v, Q6 | `rows4`, `scale8`, `wide8` | Keep the unequal contiguous 256-column split4 bounds and `(p0+p1)+(p2+p3)`. |
| Logits, Q6 | `rows4`, `scale8`, `wide8` | Keep SG32, not the faster-looking but different split4 identity. |

- `rows4`: four independent row-owning subgroups per WG128 for SG32.
  Split4 uses two independent rows per WG256, with separate partial storage.
  This removes idle subgroup work from packet 23 without assigning another
  lane to any product. Odd rows remain in barriers but cannot write.
- `wg32`: one row per WG32, retaining SG32. This is an additional scheduling
  arm, not counted as a new decode algorithm.
- `private_decode`: each lane computes its original block/subblock metadata
  locally, removing subgroup metadata broadcasts and IQ4 level shuffles.
  It retains `decode8` and its exact exceptional equations. This trades some
  repeated arithmetic for fewer collective instructions; it may lose.
- `paired_input`: the gate and up lane loops share the same eight input
  loads. The two accumulators remain independent, with unchanged additions.
  Both outputs round independently to BF16; nonlinear postprocessing is a later integration gate.
- `half_table`: only exact F16→FP32 block-scale conversion moves to load time.
  This does **not** claim to newly hoist scale work: the current kernel already
  shares it. The question is whether removing software half conversion and its
  collective costs outweighs an extra FP32 read. The two gate/up tables cost
  **629,145,600 bytes (600 MiB) per 24-layer card** for 512 experts. They fit the
  stated roughly 2.5 GB headroom; expanding all experts is not proposed.
- `staged`: every submission decodes the ten selected slots into scratch, then
  runs the qualified expanded arithmetic with the same original tree. Timing
  includes **both** kernels; their in-order dependency is explicit in the queue
  contract. It never retains expanded weights between timed submissions.
  IQ2 gate/up scratch is **42,240,000 B**, IQ3_S **37,632,000 B**, IQ4 down
  **19,456,000 B**, including scales and metadata. Codes alone are 32.768 MB
  for paired gate/up. Scratch is slot-indexed, so repeated expert IDs cannot race.
- `scale8`: load the existing FP32 scale once for each lane's eight products.
  Each octet lies within a 16/32-code scale group. No sum is factored.
- `wide8`: additionally load eight contiguous code bytes with `sycl::vec`.
  IQ4 loads the corresponding eight packed bytes and retains the exact nibble
  shift and lookup. No whole-row SLM staging or multi-block pipeline is used.

### Exceptional-value fallback

Initial tests exposed compiler-dependent NaN operand propagation in a duplicated
expression. [initial-failures.json](initial-failures.json) retains the failed
bytes. We did not canonicalize model inputs or outputs, or relax comparison.
For nonfinite source scales, nonfinite inputs, or |input| >= 2^64, candidate
**dispatch uses the current implementation itself**. CPU tests call the frozen
function again; they do not copy expected results. Device submissions select
one identical current kernel specialization for every candidate in this case.
The threshold also prevents finite overflow in admitted K≤17408 rows using
these formats. Ordinary finite, zero and denormal rows exercise the new bodies.

The standalone fixture inputs are immutable, so this classification is done
once during fixture preparation and logged as `fallback_current`. Integration
must produce that flag from the actual input and weights, including its cost;
it cannot assume every future input is finite. This flag, prologue scheduling
and the real-model oracle are explicit integration gates. CPU NaN equality does
not establish GPU NaN equality: G1 first requires current == host on the card.

## CPU evidence and independent review

The build runs both host compilers twice, compares all result fields/digests,
and checks their ELF dependencies have no accelerator libraries. It covers:

- 16,400 candidate/current/frozen-reference row comparisons, both trees,
  partial 256-column tiles, zero, signed zero, denormal and mixed NaN inputs;
- 24,576 independent per-value decoded comparisons, including special scales,
  preventing an early NaN from masking later incorrect values;
- 560 finite comparisons against an independent scalar decoder/order oracle;
- 2,430 actual routed rows, duplicate/tied route IDs and distinct slot inputs;
- 420 geometry cases, including odd rows and production boundaries;
- shared mock timing-loop tests plus mocked watcher and timing-summary tests;
- compile **and link** precision flags, platform-math grep, and an oversized
  capture rejection. The 58 emitted captures are at most 48 bytes, below 1,024.

Independent expert, dense and work-group race reviewers checked the source.
Their findings and fixes are retained in [REVIEW.md](REVIEW.md). The packet uses
our existing original kernels. Normative GGUF grids retain their existing
format-data attribution in stage1/packet1b/loaders/FORMAT.md; Intel SYCL is a
platform dependency. No outside runtime was used as the code base.

## Timing interpretation and hypotheses

G1 uses deterministic real-format synthetic packed seeds tiled over the real
row/column shapes. It is an operator diagnostic, not actual model weights or a
cold-prompt benchmark. BF16 input materialization is supplied to all arms;
upstream HC/input prologues and residual epilogues are outside this GEMV test.
The paired gate/up BF16 boundaries are included. SiLU and mixture postprocessing are outside this GEMV-only diagnostic. Selected routed-bank
fixtures contain ten expert slots, not all 512 resident experts. Cache behavior
and omitted model work must be checked again at the real-model gate.

Every shape/candidate gets 200 execution samples (GPU command_start→command_end,
summing both staged events), then 200 class-specific 48-layer-position sequences,
each with one final wait. A separate 200-repeat full 48-layer **large-GEMV-only**
sequence includes 36 GDN layers, 12 QSA layers, the upgraded layer and logits.
Its tier map records every selected candidate; unavailable/rejected arms retain
current. Tiers are joint diagnostics, not attribution of gains to one kernel.
All descriptors and pointers are uploaded once; there is no device copy per launch.

The wrapper runs two fresh owners and produces a table sorted by measured
execution ms/token saved against the matching current kernel, using the trace
frequencies. Owner rows, median and nearest-rank p90 remain visible. This is a
sum of operator savings, not a measured change in full-model token time.

Working hypotheses only: target 1.25–1.75× for gate/up, 1.2–1.6× for down,
1.1–1.25× for qkv/z/qgate and attention, and 1.05–1.15× for logits. These
are screening targets, not predictions or measured points. Expert structural
arms are the larger opportunity; dense scale/load scheduling has less headroom. Scratch decoding must repay its extra write/read traffic;
wide loads and row packing may regress. No predicted gain selects a winner.

### Retained nonlinear diagnostic

[epilogue-diagnostic.json](epilogue-diagnostic.json) records an additional
post-round SiLU test: GCC/icpx FP32 GEMV digests both `9d647ef4bc24c2fe` and
BF16 digests both `f5adec6b2b66367f`, but the optional SiLU field differs.
Its source snapshot is [epilogue-failed-sources.json.gz](epilogue-failed-sources.json.gz).
This is a retained nonlinear portability failure, not a GEMV failure or a pass.
No GEMV input fixture was removed. This packet's outputs stop at the independently
rounded gate/up matrices; it does not qualify replacement of the fused packet23
SiLU/mixture kernel. Neither NaNs nor arithmetic were canonicalized to force a pass.
