# Retained runtime constant

`rope.bf16.gz` is 1,355,545 bytes. It contains the exact 4,194,304-byte frozen
BF16 rotary table used by the qualified arithmetic. It is needed to make this
packet's runtime dependencies local. Regenerating trigonometric values under a
new compiler would introduce another arithmetic identity risk.

Restore it with `build_engine.prepare_assets()` or the normal build command.
`evidence/runtime-assets.json` binds the compressed and restored bytes. The raw
SHA256 is `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
The original remains untouched at `../packet136-record-bundle/rope.bf16`.
Only the compressed copy is tracked; `build/` is ignored. No weights or
model checkpoint bytes are retained in this repository.
