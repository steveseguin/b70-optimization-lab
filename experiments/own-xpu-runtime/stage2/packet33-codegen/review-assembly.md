# Independent reading of two expert-down dumps

The reviewer received the two assembly paths and kernel identities, without the
parent's interpretation or cost-model coefficients. This review did not use
measured times. Input hashes, block paths and exact counts are recorded in
`review-assembly.json`. The regenerated dumps explicitly use `-ze-opt-level=O2` and correctly rounded
divide/sqrt. Both final assembly hashes equal the independently reviewed initial
hashes byte for byte; all block counts below remain unchanged.

| Feature | R5 IQ4_NL down | p29 WG32 down |
|---|---:|---:|
| Dispatch SIMD / GRFs | 32 / 128 | 32 / 128 |
| Whole static GEN instructions | 2236 | 737 |
| Normal finite BF16 full tile CFG instruction sum, per eight weights/lane | 475 | 169 |
| Input messages in that tile | 8 × A64 u16 gather | 4 × A64 d32 gather |
| Scale messages | 1 × A64 u16 gather, scale-owner lanes | 1 × A64 u16 gather |
| Packed-code messages | 8 × A64 u8 gather | 2 × A64 d32 gather |
| Table messages | 8 × A64 u8 gather | 8 × A64 u8 gather |
| Total payload-data messages / eight weights | 25 | 15 |
| qword add / shift / high multiply instructions in tile | 69 / 17 / 2 | 24 / 0 / 0 |
| Payload prologue instructions / messages | 17 / 4 | 3 / 1 |
| Local-ID payload bytes | 192 | 0 |
| Flag spill-store / spill-load annotations (static) | 19 / 26 | 0 / 0 |
| Declared global private bytes per SIMT lane | 184 | 0 |
| Observed scratch-memory load/store messages | 0 | 0 |

The full tile counts use the basic-block paths written in JSON. They assume
valid full tiles, BF16 input, and normal finite nonzero half scales. They are
CFG instruction sums, not measured cycles or micro-ops. R5's scale-owner
branch has different active lanes in its two arms, so both arms are counted.
Tail tiles, exceptional scales and reconvergence can change dynamic counts.
Do not divide whole static instructions by weights and call that a dynamic
inner-loop rate. In particular R5 carries a large exceptional-scale fallback.

Both kernels dispatch SIMD32. The code says `load.ugm... (32|M0)` and zeinfo
says `simd_size: 32`. Their qword address operations frequently appear as
`add (16|M0)` plus `add (16|M16)`. This is an instruction-width split within
one SIMD32 dispatch, not two SIMD16 dispatches. A wider requested subgroup
has therefore not removed 64-bit address work.

The lookup remains an eight-message per-tile global byte gather in both
kernels. It is not a single 16-byte table block load followed by a register
lookup. The u8 messages expand into d32 results and then signed int8 values
are widened through word registers and converted to float. BF16 input
conversion is integer widening plus a 16-bit left shift, not an IEEE-half
converter. Half scale conversion remains an inlined integer decoder with
branches for normal, zero/subnormal and infinity/NaN. Subnormals retain a
normalization loop; a hardware half-to-float conversion did not replace it.

R5 has an eight-weight rolled tile body plus loop backedge. p29 statically
expands three tile bodies; all three load four packed d32 input words, two
packed d32 code words and eight u8 lookup entries. Its latter bodies carry
tail predicates. This removes the generic 64-bit tile-loop geometry but does
not remove final A64 pointer arithmetic.

Subgroup selection/reduction lowers to address-register indexing and indirect
GRF `mov` operations, typically split into two halves, followed by SIMD32
adds. No subgroup shared-memory transfer is implied. R5 additionally contains
a conditional split-reduction SLM store, SLM fence, gateway barrier and scalar
SLM block load. Its presence in the binary does not mean every dispatch takes
that branch. WG32 has no barrier or SLM messages in this dump. Neither kernel
contains a non-inlined function call.

The R5 `private_size: 5888` entry is paired with
`type: global`, `usage: private_space`, `size: 184`, `is_simt_thread: true`.
Thus 5888 = 184 × 32 is the declared global private allocation for a SIMD32
thread. It is not evidence for 5888 bytes of register-allocation scratch
spilling. The explicit spill annotations concern predicate flags copied to
GRFs; there are no observed scratch-memory send/fill messages. Reporting
these distinct resources as a single spill number would be misleading.

The payload prologue is also not the full fixed launch cost. R5 has 192 bytes
of per-thread local IDs, plus four A32 transpose/block payload reads and a
large runtime-geometry setup that includes integer-division lowering. WG32
has one A32 d32x8 transpose payload read and constant-specialised geometry.
The one-off runtime launch/submission delay is outside this assembly.

Short annotated excerpts (from the hash-bound raw dumps):

```text
R5 payload: load.ugm.d32x32t.a32.ca.cc (1|M0)  ... bti[255] ...
R5 lookup:  load.ugm.d8u32.a64 (32|M0)       ... [r64:4] ...
p29 input:  load.ugm.d32.a64 (32|M0)         ... [r28:4+0xC] ...
p29 lookup: load.ugm.d8u32.a64 (32|M0)       ... [r42:4] ...
p29 addr:   add (16|M0) ... :q ...; add (16|M16) ... :q ...
```

## Initial new-candidate dump review

Independent inspection found another source-to-GEN surprise. `down.bank`
eliminates all table gathers, but the second full tile uses eight separate u16
BF16 input gathers rather than four packed d32 gathers. Its finite normal-scale
interior path is231 GEN instructions and11 data messages per eight weights
(one scale u16, two code d32, eight input u16). The first tile has four packed
input loads and7 messages. This is not uniform across the unrolled bodies.

`down.select` also removes table loads, but the compiler introduces divergent
branches for each nested integer selection. It retains eight byte-code loads
and eight u16 input loads plus scale:17 messages per eight weights. Its
interior tile CFG sum is269–285 for a single homogeneous lookup branch path,
and461 for the union when all lookup branch arms have active SIMD lanes.
These conditional CFG sums are not measured instruction issue counts. The
source notation as nested selects did not guarantee branch-free GEN.

These first candidate dumps were sent back for source iteration, specifically
to preserve packed BF16 input loads for the bank approach. Hash-bound initial
review rows remain in JSON even if a later iteration supersedes them.
