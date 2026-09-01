# Qwen3.8 Flash-Next FP8 A39 checksum-rewrite negative

Date: 2026-09-01
Status: preserved pre-load generator negative

A39's three outer reads of the frozen graph-safe oneCCL library all matched the
correct SHA-256. The generated inner launcher then failed its own check before
starting a model server or loading a checkpoint. This was deterministic: the
successor generator globally replaced `a38` with `a39`, including the
characters embedded in every inherited checksum literal.

The generated launcher, client, and supervisor respectively contained three,
three, and two copies of the incorrect digest ending in `d3a39fad6700`, and no
copy of the correct digest ending in `d3a37fad6700`. The clean outer checks and
direct reads therefore behaved correctly. No performance or quality credit is
assigned, protected results are unchanged, and no reboot is needed.

A40 preserves the inference identity and introduces a fail-closed repair: after
the path/attempt rewrite, it must replace the exact corrupted digest a fixed
number of times for each generated source mode. Any count drift aborts source
generation. Static validation also requires every resulting literal to equal
the pinned library digest before launch.
