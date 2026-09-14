# Decoder axis cache: corrected packet10 source preparation

2026-09-14. Packet09 failed private-node registration before any clip request or
router installation: its node pinned upstream `comfy/sd.py`, while the sealed
encoder runtime inherited a modified file. Hashing each file separately did not
check whether the node's declared dependency hashes matched those files. The CPU
node lifecycle test bypassed `initialize()`, and the client computed actual
source hashes without comparing the node's constants.

Packet09 and its builder remain unchanged. The successor
[`prepare-na-axis-runtime-v2.py`](../scripts/prepare-na-axis-runtime-v2.py) still
inherits the numerical source and launcher from packet08. It uses the corrected
[`na_axis_decode_node_v2.py`](../scripts/na_axis_decode_node_v2.py), with the
inherited `SD_SHA` and a specific module name in source-mismatch errors. Sealed
custom-node and helper filenames remain unchanged.

Preparation and the generated packet checker now parse literal startup pins
without native imports and compare all seven node/router dependency edges
against actual source bytes. Missing, duplicate, conditional and nonliteral pin
declarations fail closed. The same generated helper runs whenever the packet is
verified. The manifest binds the closure receipt and copies of packet09's
manifest and startup failure JSON/log, preserving the failed integration as
correction provenance.

Evidence:

- [Sealed summary](../data/na-axis-runtime-10/summary.json),
  [manifest](../data/na-axis-runtime-10/manifest.json), and
  [checker patch](../data/na-axis-runtime-10/runtime.patch).
- [Source checks](../data/na-axis-runtime-10/source-checks.json) and
  [19 stdlib regression checks](../data/na-axis-runtime-10/source-regression.json).
  These reproduce packet09's hash mismatch and pass the corrected closure;
  dependency and declaration mutation tests reject malformed inputs.
- [Unchanged launcher check-only](../data/na-axis-runtime-10/launcher-check-only.log)
  passed for `encoder-server-na-axis-10`, with no device discovery, locks,
  process changes or GPU work.

Packet path:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-10`.
Manifest SHA256:
`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.

This records inactive preparation only. The source checks do not establish
actual native registration, full-clip parity, speed, or streaming qualification.
The next gate is the controlled application startup and bounded, unchanged
original/cache/original screen owned by the root agent; no native workload or
process action was performed for this preparation review.
