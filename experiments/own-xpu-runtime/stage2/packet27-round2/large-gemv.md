# Large GEMVs: second round, CPU preparation only

No device was opened or executed during this preparation. All times below are
hypotheses for coordinator K2, never measured packet 27 results.

The packet 26 incumbent is the actual integrated R5 entry for every GEMV class.
Its paired expert entry remains a paired entry in both arms. K2 instantiates
production formats and shapes and compares that actual entry with **every**
registered bridge alternative. It records the comparison candidate on both arms,
implementation identity, byte equality and per-arm execution-sum median/p90 in
microseconds. Each candidate has a separate control sequence in the same owner.
Failures exclude that arm and continue to the next candidate. There is no
candidate column that silently calls R5. `same_kernel=false` means a distinct
submission/kernel body, not an assertion that the compiler emitted different ISA.

The retained packet 25 alternatives are rows4 for every supported class; wg32,
private_decode and paired_input for packed expert gate/up; wg32, private_decode,
wide8 for packed IQ4 down; scale8 and wide8 for expanded dense matrices. The old
staged decode-then-GEMV arm is deliberately absent as instructed. The historical
half_table arm requires a separate persistent scale-table representation that
this runtime does not have, and is not a registered runtime alternative. Its
source helper remains preserved as provenance rather than being relabeled as a
working candidate.

| Class and model shape | Old microseconds | Named candidate | Hypothesis, microseconds |
| --- | ---: | --- | ---: |
| expsgate IQ2/IQ3, paired 10 x 640 x 2560 | 178 | p25.wg32 | 165–175 |
| expsgate same | 178 | p27.fp32_input | 140–165 including preparation |
| expsdown IQ4, 10 x 2560 x 640 | 130 | p25.private_decode | 115–125 |
| expsdown same | 130 | p27.rows2sg | 90–115 |
| expsdown same | 130 | p27.packed64 | 100–120 |
| expsdown same | 130 | p27.fp32_input | 110–125 including preparation |
| gdn.qkv Q6/Q8, 10240 x 2560 | 101 | p25.rows4 | 80–90 |
| gdn.qkv same | 101 | p27.fp32_input / p27.packed64 | 75–95 |
| gdn.z Q6/Q8, 6144 x 2560 | 62 | p25.wide8 | 48–55 |
| gdn.z same | 62 | p27.fp32_input / p27.packed64 | 45–58 |
| qsa.qgate Q6, 12288 x 2560 | 118 | p25.rows4 | 100–110 |
| qsa.qgate same | 118 | p27.fp32_input / p27.packed64 | 95–110 |
| attention Q6, 2560 x 6144 | 67 | p27.fp32_input / p27.packed64 | 55–65 |
| logits Q6, 248320 x 2560 | 2140 | all dense alternatives | 1900–2300 |

## FP32 input vector

`prepare_input` creates the FP32 value by shifting the exact BF16 bits, with no
floating-point conversion operation. Each later product receives the same FP32
operand that the original inner loop formed. Weight decoding, lane assignment,
per-lane product order, additions, subgroup tree, split tree and BF16 store are
unchanged. The kernel still decodes each weight directly; no decoded weight
matrix or staged weight GEMV exists.

The runtime allocates 696,320 bytes of reusable FP32 scratch per card. It caches
only one source allocation and element count at a time. A writer of that BF16
source invalidates the cache, as does every token lookup. Thus qkv/z or other
siblings sharing the same still-live source may use one conversion. If another
candidate overwrites the float scratch, the source key changes. Expert gate and
up share one preparation for both projections and all 12,800 output rows. Routed
down has ten independent input rows and converts all ten. Preparation is an
ordered device kernel, with no host/device copy per launch, and is charged to
class timing. K2 conservatively includes preparation in every candidate sample.

## Packed 64-bit code loads

Expanded Q6/Q8 rows consume eight signed codes with one eight-byte vector load
whose bitcast is a 64-bit word. Extraction changes only integer access, leaving
the scale-times-integer expression and subsequent input product unchanged.
IQ4 code bytes are shared by virtual lanes differing by bit 1 (nibble halves of
the same 32-weight block). The owner loads the eight bytes once; a subgroup
broadcast distributes the word to its second owner. Each lane selects its
original nibble and retains its original scalar scale/product order. Every lane
participates in the subgroup collective, even on the partial last tile; inactive
lanes use an in-bounds dummy word and never accumulate it. No packed pointer is
cast to an unaligned uint64_t pointer.

## Two short rows per subgroup

For IQ4 K=640 only, physical lanes 0–15 own one row and lanes 16–31 the next.
Each physical lane retains two independent accumulators for the original virtual
lanes `lane%16` and `lane%16+16`. The original high virtual lane has no terms in
the partial third tile, so all physical lanes still have a live low virtual lane
to process. Products and additions within each virtual lane are unchanged.
Reduction widths 1, 2, 4 and 8 are applied independently to both virtual halves;
then the two virtual roots are added at width 16. This is the original tree,
including operand order, not a new 16-lane reduction. Each row has one writer,
rows never share accumulator storage, and no workgroup barrier is needed.

## Fixture scope and selection

K1 enumerates every registered candidate over four finite BF16 fixture modes,
including signed zero, subnormal scales/inputs and finite extremes. Each matches
the unchanged arithmetic reference and the runtime R5 output. Production K2
geometry is retained for argument validation, while CPU K1 uses eight output
rows to bound cost. Mini integration uses its original packed arithmetic for
large-GEMV labels: these model-specific candidates require production layouts.
The independently instantiated mini small-GEMV tuples and non-GEMV round2 paths
remain active. The full real-model eight-token gate exercises the actual large
GEMV candidates named by all-new dispatch. New entries remain opt-in until exact
K2 comparisons beat the packet 26 incumbent by strictly more than 10 percent.
