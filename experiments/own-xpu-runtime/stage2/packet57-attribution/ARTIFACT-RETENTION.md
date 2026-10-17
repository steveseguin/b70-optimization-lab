# Packet 57 artifact retention

The CPU build is capped at **1,000,000,000 bytes**, under
`/home/steve/own-xpu-runtime-results/packet57-attribution/build`. Retain final
binaries, compiler commands and logs, checked source mirrors, CPU receipts,
the seal, and all future device evidence. Only this packet's regenerable
objects and successfully summarized synthetic scratch may be removed.
Preserve failed checks and their diagnostic files. No cleanup may touch
packet 55, a parent packet, oracle, model tree or unrelated scratch.

`rope.bf16` is the one source artifact above the repository's 1 MiB retention
review threshold: **4,194,304 bytes**, SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
It is packet 56's unchanged numerical RoPE table, required by the identical
target/draft arithmetic and bound by the source manifests and seals. Restore
its exact Git blob or copy the parent file and verify that hash. Do not
regenerate it through another math library. Git reuses the identical blob;
both source snapshots retain their required path.

The timeline summary is compact and hash-binds retained external receipts.
Raw per-rank traces and future event logs stay in their existing or newly
registered result directory. Model weights and compiler caches are not Git
artifacts. The `build` link is a local result-location pointer, not a claim
that its files are publicly reproduced.

The coordinator's later output budget is separate from the CPU build cap.
Its storage gate preserves the 8 GB free-space floor and refuses inadequate
space; it never deletes another packet to admit the window.
