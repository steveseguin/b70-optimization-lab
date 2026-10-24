# Batched prefill on the F32 exact engine: implementation plan (2026-10-24)

The service runs the F32 exact mode (`--activations f32`), so batched prefill is built for that mode first, and the
BF16 mode keeps refusing it. The design work in [DESIGN.md](DESIGN.md) targeted the BF16 engine 5926 and full-dump
identity. This plan reuses its analysis but changes the gate (below).

## Gate (lossless)

Against the same binary's scalar prefill, all of the following must be identical:
- every emitted token, target-only and with MTP;
- every MTP guess;
- the persistent state that can influence later output, compared logically (by the active bank's contents, not by the
  physical bank name). It covers:
  - KV keys and values;
  - indexer raw and pooled vectors;
  - the active GDN recurrent state and conv history;
  - PLE history;
  - host and device token history;
  - position;
  - draft state.

Scratch and overwrite-only intermediates are excluded, because nothing reads them before rewriting them. No tolerance.
Prompt lengths cover 31/32/33, 63/64/65, pooling 3/4/5 and odd/even chunk tails.

## Why rows are identical by construction

- **ng kernels.** They already loop rows inside one work-group, with the same arithmetic as tokens=1:
  - GDN and conv carry state row to row, reading the input bank at row 0 and the output bank afterwards;
  - select and attention bound each row to `pos+r`;
  - pool finalises only complete groups.
- **GEMV families.** These take a token template count R. They decode each weight once and apply it to R accumulators,
  each with the unchanged per-row product, add and lane-tree order. R=1 is the existing kernel.
- **p49 split32 attention.** It is per-row independent. Only its counts header (hard-coded 16 bytes, so at most 4 rows)
  must be generalised to `align_up(4*M,16)`.

## Structure (reuse, not fork)

1. **`flash::Builder`.** Add a prefill section to the same plan: labels `pf.blk.N.*`, buffers with a leading M
   dimension, and intermediates named without the layer number so all layers share them. Persistent buffers (keys,
   values, raw, pooled, gdn.state, gdn.history, ple.history, token_history, position) use their decode names, so they
   are the same allocations. The decode `half_step` skips `pf.` launches.
2. **Engine.**
   - `matrix()` gets a count M per-slot input for `pf.` gemv sites, and routed sites get M×top slots.
   - `prepare_site` sets `ng::Shape.tokens=M`.
   - `admit_position` covers `pos+M`.
   - commit adds M.
   - PLE/embedding host preparation runs once per row, in order.
3. **Rank op `PREFILL` (new opcode 12).**
   - Its input is the start position and M tokens, from a new versioned shared region placed after the existing
     266,304-byte map; the old offsets are unchanged.
   - Rank 0 writes M forward stream rows.
   - Rank 1 reads them and writes M reverse rows (final-layer streams) for the draft.
   - Rank 0 swaps the recurrent banks once, as the scalar HALF does.
4. **Controller.**
   - Bulk positions 0..N-1, where N = P−2, in chunks of M.
   - Rank 0 runs chunk k+1 while rank 1 runs chunk k.
   - Rank 0 replays the draft for each confirmed position 1..N-1 in order: it copies reverse row r into the existing
     reverse slot with tag pos+r+1, then calls the unchanged DRAFT.
   - Seam: run the original rank-0 HALF(N)+ACCEPT and DRAFT(prompt[N], N), then enter the unchanged scalar loop at
     p=N with `draft_pending`.
   - P ≤ M+2 uses the unchanged scalar path.

## Order of work

1. Typed GEMV R-token kernels plus a host-only CPU identity test (rows R vs repeated R=1).
2. Builder prefill section, engine plumbing, `PREFILL` op, and the per-rank state-hash command.
3. Controller bulk and seam.
4. Device gate (service stopped for the window, then restarted), then timing.
