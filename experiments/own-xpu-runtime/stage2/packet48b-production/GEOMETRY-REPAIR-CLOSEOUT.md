# Packet48b repack geometry repair

Question: does the full-layer compact-layout adapter preserve all producer and
state bytes against the actual packet45 engine?

The first host fixture refused during synthetic weight repacking with
`p48 row geometry`, before comparing or running any device. The adapter used
`t.shape[1]` as K for every descriptor. That is K for a dense matrix, but the
row-major routed descriptor is `[experts, rows, K]`; its second dimension is
the output row count. The fix uses `t.shape.back()` for both ranks. Full bank
row count remains `t.bytes / raw_stride`, and the typed issue path separately
checks its registered K.

The rejected source, both passing compilation receipts and failed CPU gate
receipt are retained at `evidence/geometry-rejected/`. The exact first failed
run is `evidence/cpu-layer-20261017T034326.533255Z/repeat-1/`; it shut the CPU
mock down safely with zero live allocations. No GPU or model payload was used.
The current host/device builds and both complete CPU fixture repeats must pass
before a seal can be written. This error was in the new adapter, not in the
sealed packet48 arithmetic or packet45 engine.

Revisit if tensor rank or loader orientation changes. Infer K from the final
row-major dimension and retain the complete production-size fixture gate;
a row-zero or dense-only mock would not have caught this expert-bank error.
