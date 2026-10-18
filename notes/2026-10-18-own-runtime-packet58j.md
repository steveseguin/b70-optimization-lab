# Packet58j: one-card target port

CPU preparation started from a separate copy of packet58g. The initial pull
refused existing unrelated edits; fetch confirmed local main equals origin/main.
No other work was stashed or changed. Frozen source hashes are retained.

Down-tile16 will transpose packed chunks at pin time, so both cache fills and
zero-copy misses see the same layout. Route-fast and rec-both-plus are selectable.
E1 adds 616,038,400 host-pinned bytes and is excluded under the unchanged
58g budget. No GPU, service or host setting is changed.

The port now passes all 80 full-size startup and submit checks: eight views,
five model windows, and both zero-copy and streamed misses. Each checks short
and full context and reproduces the old p28 pointer-table refusal. All 3,446
arena rows retain 24,287,732,980 device bytes and 48,633,091,712 pinned bytes,
including staging. All 56 view/window admission plans equal 58g.
The GNU engine builds; Intel byte and device compilation are still in progress.

The proposed bracket uses production / port / production, then a separate
fresh record chain only if it beats both controls and the saved record, with
controls within 3%. Every window holds the whole host and rejects lane B.
