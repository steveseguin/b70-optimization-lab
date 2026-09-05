# A141/A142: sub-operation attribution of the two-row step (2026-09-04, 21:47-22:09)

Eager deterministic identity at 4352 tokens (A83 lineage), one exact-2K
request each, with the overlay's device-synchronized sub-operation hook
(`Q38_LAYER_TIMING_LOG=10`, level >= 2, overlay `fd686ba8`): every mark
calls `torch.accelerator.synchronize()`, so the numbers are wall time per
model forward summed over the 48 layers, inflated by the syncs (eager
forward 234 ms at M=1 against 71 ms for the graph replay), and only the
M=1 to M=2 deltas are meaningful. A141 is MTP1 with the three exact-verify
selectors (M=2 verification rows), A142 is MTP0 (M=1). Both requests
returned the authority hash `afffd211...`.

| sub-operation (ms per forward, median over logged steps, TP0..TP3) | A142 M=1 | A141 M=2 | delta |
|---|---:|---:|---:|
| MoE experts kernel | 51-52 | 75-102 | +24..+51 |
| MoE reduce and combine (final TP all-reduce, shared add) | 18-26 | 104-141 | +80..+120 |
| GDN core (serial verifier rows through the decode kernel) | 4.5 | 25 | +20 |
| GDN out_proj (row-parallel, TP all-reduce) | 8-9 | 32-39 | +24..+30 |
| GDN in_proj / norm | 6 / 6 | 7-10 / 6 | ~0 |
| QSA qkv_proj / indexer / attention kernel / o_proj | 7 / 19 / 4.4 / 3 | 8 / 20-21 / 4.9 / 6 | +1 / +1.5 / +0.5 / +3 |
| layer totals: gdn_attn / qsa_attn / mlp / hc_mix | 30 / 35 / 80 / 73 | 76-83 / 42 / 210-215 / 88-102 | +50 / +7 / +132 / +20 |
| step forward / drafter / sampler | 234 / 0 / 1.0 | 400 / 12 / 1.1 | +166 |

The MoE block pays about 130-155 ms of the 166 ms two-row delta in the
eager run: the expert kernel itself grows 1.5-2x (per-expert launches
scale with the number of distinct experts the two rows hit), and the
segment after it, which is dominated by the final TP all-reduce, grows
4-6x. Because that all-reduce is a collective, its wall time absorbs the
rank skew of the expert kernel (75 ms on TP2 against 102 ms on TP1), so
the sum of the two MoE segments per rank (201-230 ms at M=2, 70-77 at
M=1) is the honest MoE cost. The serial verifier-row GDN path adds about
20 ms of kernel time plus 25-30 ms in the out_proj segment (the same
all-reduce skew effect, two row-wise calls per layer). QSA and the
hyperconnection mix are near-flat.

Caveats: the eager step includes ~160 ms of launch and sync overhead that
the graph replay removes, and the graph-mode subtraction runs (A129,
A130) showed that dropping the row-wise all-reduce or the row-wise norm
does not shorten the size-2 replay, so the all-reduce call count is not
the cost; the M=2 MoE kernel time and the serial GDN path are. Next:
graph-mode skip diagnostics (replace the expert kernel, then the GDN core,
with a no-op under `Q38_DIAG_SKIP`, timing only, outputs discarded) to
measure each block's replay cost directly, then a small-M MoE path.

Data: `../data/20260904-tp4-mtp1-a141-subop-timing-2k.json`,
`../data/20260904-tp4-mtp0-a142-subop-timing-2k.json`,
`../data/20260904-tp4-mtp{1,0}-a14{1,2}-exact-depth-2k-r1.json`
(reduced with `../tools/summarize-q38-subop-timing.py`). A141's first
launch (11:21) and the A143 relaunch (22:12) coincided with silent host
freezes; the frozen directories are kept as `*-frozen-1122` and
`*-frozen-2212`.
