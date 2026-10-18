# Packet58j: one-card target port

CPU preparation started from a separate copy of packet58g. The initial pull
refused existing unrelated edits; fetch confirmed local main equals origin/main.
No other work was stashed or changed. Frozen source hashes are retained.

Down-tile16 will transpose packed chunks at pin time, so both cache fills and
zero-copy misses see the same layout. Route-fast and rec-both-plus are selectable.
E1 adds 616,038,400 host-pinned bytes and is excluded under the unchanged
58g budget. No GPU, service or host setting is changed.
