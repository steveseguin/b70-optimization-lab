# Packet58j decisions

- E1 half-cache is excluded under 58g's unchanged pinned-bank budget. Its IQ2
  scale expansion adds 616,038,400 bytes over the 47 IQ2 layers. Revisit only
  with an explicitly different admitted budget; never shrink the cache or
  reserve to conceal the extra allocation.
- Down-tile16 must reach the pinned bank before any cache publication. Both
  zero-copy misses and copied cache slots read that same layout. Never pass
  the expert pointer table to a direct packed-bank submitter. Keep the full
  arena startup/submit gate; a miniature fixture alone missed the p28 defect.
- All one-card model windows exclude lane B. A two-card lane-B memory screen
  cannot coexist with the roughly 85.6 GB one-card model admission. Timing
  retains the full 118.3 GB requirement and all host/memory-block rules.
- No draft, MTP, compressed KV, prompt reuse or CPU-computed expert misses.
  Packet58h's MTP closure and packet58i's attribution limits still apply.
- GNU and Intel each must match the unchanged reference in raw bytes. Preserve
  any cross-compiler baseline NaN-payload differences explicitly; never normalize
  NaNs or change the target arithmetic to manufacture equal transcripts.
- A two-card win is not a one-card measurement. The proposed matched bracket
  and fresh confirmation are pending; no throughput is inferred here.
- Pin immutable sources, selections, oracle inputs and completed CPU gates.
  Never pin a live queue, readiness report or changing composition decision.

See [58g's inherited cautions](../packet58g-onecard/DO-NOT-REPEAT.md),
[58h](../packet58h-onecard-mtp/DO-NOT-REPEAT.md),
[58i](../packet58i-onecard-attribution/DO-NOT-REPEAT.md), and
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
