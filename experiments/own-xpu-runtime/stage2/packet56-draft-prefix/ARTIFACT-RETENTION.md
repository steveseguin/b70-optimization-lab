# Packet56 artifact retention

Only this packet's regenerable object files and compiler scratch may be
removed. Keep compiler commands/logs, source mirrors, final executables,
CPU gate receipts and future device evidence. The external build path is
`/home/steve/own-xpu-runtime-results/packet56-draft-prefix/build`.
No cleanup touches a parent packet, running chain, oracle or weight tree.

The build peak is capped at 1,500,000,000 bytes. The inherited chain admission
retains an 8GB root free-space floor and separately budgets its own future
chain. Device work waits for packet49d to finish; preparation does not retire
or delete that chain's evidence. The root had about18GB free at entry.

`rope.bf16` is a 4,194,304-byte source artifact, deliberately retained despite
the repository's 1MiB review threshold. It is the unchanged packet49d RoPE
table used by this source snapshot and covered by both parent and new build
seals. `base-source-manifest.json` pins its original digest. Restore exact
bytes from that Git object or the parent file and check the digest; do not
regenerate it using a different math library. Git deduplicates its identical
blob, but this is not a reason to remove either packet's source reference.

The calibration histogram and compact timing analysis are tracked. Raw
packet45/49c timings stay at their existing locations, with paths and hashes
in the analysis receipt. No model weights or generated caches enter Git.
