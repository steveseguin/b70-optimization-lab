# Capacity 4,096: source argument and measured gate

This extends the suite128 capacity argument without changing a numerical operation.
The original numerical sources remain read-only. A generated host-only adapter overlay
changes two scratch allocation/bound constants, as explained below.
`build-receipt.json` binds the sealed arithmetic source map and compiler flags;
`oracle_long.cpp` includes packet17 `runtime_main.cpp` exactly as the sealed wrapper.
The wrapper sets Options.context=4096; it does not use runtime_main's old CLI parser.

- packet17/runtime_main.cpp, plan(): copies Options.context to Geometry.context.
- packet3/step/plan.hpp:163–171: sizes keys, values, raw and pooled storage from
  context; QSA head dimensions, budget and selected-ID buffer remain unchanged.
- packet17/runtime_kernels.hpp:77: begin rejects position >= context.
- packet17/core_v2.hpp:383–424: append/pool reads only positions <= current;
  complete pools number (position+1)/4, trailing positions are admitted separately;
  ranking and stable tie order do not depend on capacity.
- packet17/core_v2.hpp:425–456: attention reduces only the selected valid positions,
  in the same ordered reduction. No padded capacity suffix enters that reduction.
- packet17/rope.hpp uses the frozen 4,096-position table by position and coordinate;
  it is neither regenerated nor rescaled. The wrapper asserts the table bound.
- Other operator shapes and arithmetic, BF16 KV and recurrent state, the weight
  admission, dequantization, trees, compiler flags and deterministic math stay fixed.

Therefore 192/256 -> 4096 changes allocation extents and bounds, not arithmetic for
positions valid at both capacities. This is specific to this CPU implementation.
It says nothing about a different device kernel or context beyond the frozen table.

The required measured gate is capacity-incident/equality-proof.json: rerun the
sealed 87-token incident at 4096 and compare all 64 generated token IDs, all logit
hashes/top-five records, 384 raw layer fixtures and eight hash ledgers byte for byte.
Only after that gate passes may LONG-A start. LONG-A's completed validation gates
LONG-B. The longer contexts are new oracle coverage, not inferred device equality.

The wrapper also checkpoints every complete 100 positions, copies selection buffers
and audits pool scores at retained positions. These operations observe state only.
They do not prune a layer, change a reduction, compress KV or substitute a kernel.
The checkpoint proof interrupts a six-token diagnostic in prefill and generation,
then compares its complete eight-token result and retained bytes to an uninterrupted
run. Resume restores all plan buffers and regenerates transient workspaces/weights.

The input bundle builder takes only a rendered prompt. tokens.txt, input.json,
identity.tsv, plan.tsv and vocab.bin encode no context or generation cap. Old runtime
CLI limits (1024 context in packet17) are launcher bounds, not input-format bounds;
packet44 owns the device-side extension. This task never changes its files.

## Temporary pool capacity

The source review found an independent allocation bound: the frozen CPU adapter uses
a 256 MiB monotonic pool for all temporaries in one operator. The attention operator's
retained temporary vectors exceed that at long admitted lengths. The local
`scratch-capacity.patch` changes Engine's backing allocation to 512 MiB and evaluate's
float-slot bound to 128 * 1024 * 1024. Both must change together. This is temporary
working storage, not KV compression, not model precision and not a reduction change.
Every expression, allocation order and resulting vector length is otherwise identical.
`build_cpu.py` relocates quoted includes into the local overlay to apply exactly these
two substitutions, checking each original literal occurs once; the build receipt
binds the generated sources as well as the sealed originals.

The initial capacity replay was stopped cooperatively after this finding, before
any numerical pool failure. Its incomplete receipts remain in
`preparation-stopped-capacity/`. The final enlarged-pool binary must pass the full
sealed incident comparison and interruption/resume comparison before LONG-A.
