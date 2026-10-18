# Retention

Keep this packet's copied native sources, all links, bindings, generated source
patch, CPU receipts and probe plan. Keep raw device events, both model windows,
state-equality verdicts and fault/drain receipts under evidence/probe-B, within
200 MB. They are ignored for Git until reviewed; do not remove them based on a
summary. No model weights or full mutable-state snapshots are copied to disk.

Build outputs are ignored and reproducible by build_engine.py and full_shape.py
against their hash-bound original kernel objects. Parent objects are required
reproduction dependencies, not disposable caches. Copied links are reproduced
by preserve_links.py from symlinks.json. The oracle authority stays external.

`rope.bf16` is 4,194,304 bytes. Retain its exact packet136 bytes because the
owner requested a frozen source copy including runtime constants. It is consumed
by the inherited rope loader and provenance checks. Restore it from
`../packet136-record-bundle/rope.bf16`, verifying `copy-provenance.json`; do not
regenerate or deduplicate it without changing the frozen-copy contract.
Inherited whitespace in p109_route.hpp and the exact prompt is retained on
purpose. The generated unified patch includes an ordinary blank context line.
