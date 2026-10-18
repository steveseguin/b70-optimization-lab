# Packet99: exact expert lookup representations

CPU preparation only. Source base: frozen packet97 bundle, recorded in
`copy-lineage.json`. No existing packet, screen tree or live queue is edited.
Production is wide64, hc-wide, ordered, rec-parallel. The packet97 head,
reply-first, norm, route and recurrence dimensions remain implemented; a new
combination still needs its own exactness and performance qualification.

## Mechanisms and decision

1. `exp-slm`: cooperate across WG64 to fill the original 8 KiB IQ2 grid once,
   barrier before any route-dependent branch, then read grid words from SLM.
2. `exp-compact-slm`: encode each normative magnitude (8, 25, 43) in two bits,
   fill a 2 KiB SLM table, read one packed word and decode eight magnitudes.
3. `exp-compact-global`: the same exact 2 KiB table in program constant data;
   retain global lookup but halve dependent load width and shrink footprint.
4. `down-byte-slm`: IQ4_NL has no IQ2 grid. A 512-byte logical byte-to-two-level
   table (packed in 128 words) replaces the two nibble bank-selection paths.

The first three also have explicit `+halfcache` forms, preserving packet97's
840-byte row stride. E1 is a composition option, not a standalone speed claim.
No grid-prefetch, full scale cache or HC weight cache arm is reopened.

All arms retain the same scale multiplies, signed integer values, exceptional
NaN/Inf arithmetic, FP32 products and additions, logical chain traversal,
adjacent reduction tree, BF16 output, routing and error writes. Arithmetic
identity remains `iq3-p49-split32-v1`.

Packet81 deferred SLM because prior packet52/53 schedules lost. Packet86 now
provides distinct measured dependency-latency evidence. This arm uses production
WG64 virtual chains, not persistent scheduling, and explicitly measures fill
and barrier cost inside the timed kernel. Compact SLM reduces fill by four.

## Gates, in order

- GNU and Intel exact raw bytes, full expert shapes, invalid routes, tails,
  exceptional values, raw FP32 logical chains and adjacent trees; repeated runs.
- Linked offline BMG assembly: actual local loads, table representation and
  zero spill/scratch metadata. Retain failed candidates rather than promote.
- Actual full-size engine startup, arena allocation and capture with only model
  payload/backend mocked; both ranks, short/misaligned extents and invalid
  selections. Keep 30 GiB arena and 1.5 GB VRAM margin unchanged.
- Hash-bound CPU seals and temporary queue planning.
- Coordinator-only single-card full-shape microbenchmark, 40 alternating
  control/candidate pairs. Exact outputs required; candidate must take at most
  85% of control kernel time overall and in each order. Synthetic diagnostic
  only, never a model benchmark. No device launch in this CPU-only task.
- Each qualified candidate gets its own B control/candidate/control bracket,
  followed by the same A bracket. All 13 exact checks and unchanged per-prompt
  acceptance required. A decides record selection; records run on A. No speed
  verdict or headline before actual evidence, and no full chain launched here.

Budget: three hours; nice 19, CPUs 8–15/24–31, stdin closed, Python -B,
8 GB address-space ceiling and serialized packet94 compiler lock. Build stays
below 500 MB; retain compressed receipts before deleting fixture scratch.
