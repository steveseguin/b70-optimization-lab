# Packet109 retention

Keep the copied source closure, concrete fusion kernels, overlay, provenance,
all gate receipts, compiler/run logs, compressed exact-byte output streams,
full-shape capture archives and rejected NaN variants. These establish what was
tested and explain why superficially equivalent expressions were rejected.

Full-shape scratch is archived with a member-by-member byte comparison before
removal by `retain_shape.py`. Byte streams and census JSON use lossless gzip;
the uncompressed census is generated scratch. No existing experiment evidence
is removed. The generated RoPE header is excluded from Git and restored from
the hash-bound original by `restore_rope.py`. Build products and native generated
sources are excluded from Git, remain locally sealed, and reproduce with the
README sequence. Unchanged linked object dependencies are recorded by hash.

The local build is capped at 300 MB and process address space at 8 GiB. No host
memory, swap or cache settings are changed. Parent files and live queues are
read-only. No full-model output or performance receipt exists until the proposed
device bracket runs; its retention follows the inherited v5 screen protocol.
