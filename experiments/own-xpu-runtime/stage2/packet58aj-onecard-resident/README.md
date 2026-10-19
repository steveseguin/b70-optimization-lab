# Packet58aj: full one-card composition with resident lookup copies

This is a private, symlink-preserving copy of packet58ah. Its native source
and bracket harness are vendored from the exact packet58ag engine used by
58ah. Packet58t supplies the complete packed-tensor copy implementation.
Existing packets remain frozen. Preparation does not queue or launch anything.

The experiment addresses fresh-window paging. Both complete lookup tensors
are copied at load, SHA256-checked and made read-only: Q6_K `token_embd.weight`
(521,472,000 bytes) and IQ4_NL `per_layer_token_embd.weight` (28,800,138,240).
`--lookups mapped|resident` changes only where those unchanged bytes are read.
All rows are copied; allocation/copy failure refuses the candidate. No page
advice, pre-read, mlock, sparse fallback, swap or host settings are introduced.

Every view keeps HC fusion, HC-wide, wide64+halfcache, other-fusion, ordered
foreground retirement, tile16, overlapped maintenance, zero-copy misses and
the 21,552,729,600-byte device cache. KV stays BF16 at context4096. The oracle
is unchanged `iq3-p49-split32-v1`; this is the quantized compressed version.

The smoke analyzes its own output immediately and checks real output as it
appears, then checks all twelve 64-token responses. The one-load v5 order is
mapped/resident/mapped/resident/mapped, twelve 128-token responses per view.
A0 is exact and reported as warm-up. Both resident views must be within
inclusive ±0.5% of both warm mapped controls. Neutrality is sufficient because
the purpose is stability across fresh loads. Copies are retained in mapped
views too, and loading them warms source pages; this is not a cold-disk test.

[WINDOW.md](WINDOW.md) is the coordinator contract. [MEMORY.md](MEMORY.md)
shows the production allocation accounting. The seven-window chain uses
`lookups=resident`, freezes Codex from WS, and requires its own smoke and v5
before launch. Only its fresh WS128 can supply a new timing. The predecessor
is now 58ah chain b, 31.66271941826957 tok/s, submitted as
`cmvekebvh00a0rf01q3v2c3cz`. Both prior attempts remain disclosed.

CPU proof checks bounded synthetic packed bytes using actual production row
widths (2,560 Q6_K and 160 IQ4_NL values), both compilers, repeats, actual
engine resets and exact equality to 58ah's host engine. The full 29.32 GB
production copy is a future device-window allocation; CPU preparation does
not allocate it or read model payload. New device equality and performance
remain pending. No synthetic timing is a measurement or record.

Build with `build_engine.py` after the two-card preparations; every compiler
turn passes through `ops/compile_turn.py`. `native/generated` retains the exact
entry source snapshot; `lineage/58ag-build-commands.json` records the parent
commands. The two-card priority, 4 GiB RSS limit, 300 MB build cap and 27 GB
root stop floor apply. Python subprocess wrappers have no wall timeouts that
would count frozen time. Historical snapshot scripts are evidence only.

[Work note](../../../../notes/2026-10-19-own-runtime-packet58aj.md).
Final readiness markers are written only after all requested checks and pushes.

## Retained lookup fixture

The private `frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.bf16` is 4,194,304 bytes. It is retained because the inherited loader/entry contract needs these exact rotary-table bytes; this is a small runtime table, not model weights or a generated cache. SHA256: `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`. Restore it from this packet's tracked Git blob; do not regenerate arithmetic or borrow a mutable sibling table. Native executables and object files remain ignored, with `restore-inputs.json`, `restore_build.py` and build commands retaining their hash-bound local restore path. This research packet is not a publicly reproducible release.
