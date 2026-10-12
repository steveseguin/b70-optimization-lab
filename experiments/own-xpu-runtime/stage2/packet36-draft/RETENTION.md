# Evidence retention

The official-tensors.json manifest may exceed 1 MiB. Retain it: all 3101 official
MTP tensors and every publisher-authenticated containing file are required to
review exactly which bytes the draft reads. It contains metadata and hashes,
not model weights. Rebuild it with prepare_mtp.py against the revision-pinned
local official checkpoint and packet1 contract; publisher hashes must match.

Build binaries, captured inputs and KD CPU fixture bytes stay in ignored build/
for the coordinator. Durable JSON receipts and source hashes bind them. Scratch
gate directories are removed only after retaining their small receipts and
byte-comparison counts; cleanup never touches another packet, source model,
coordinator input, binary or a retained failure owner.

The 20,024,756-byte preparation-log archive retains 8,192 completed CPU test
receipts, command traces and failure/ownership records before 1.75 GB of
regenerable test scratch was deleted. It supports review of provider fallback,
rollback, command order and teardown beyond the consolidated pass counts.
The matching scratch-cleanup receipt records its SHA256 and verified every
restored member's original bytes. To restore, decompress the gzip JSON, decode
each base64 member, check byte count and SHA256, and write only its recorded
packet36-relative path. No model weights are archived. Keep this evidence;
size alone is not permission to discard it. The final build receipt may also
exceed 1 MiB because it binds all official tensors and retained KD fixture files.

Superseded draft fixture copies are removed only after their repeat receipt
proves every BF16/cache byte equal to the retained final-binary capture. Historical
capture records gain restoration pointers before deletion. The cleanup receipt
lists every duplicated file hash and its retained source; the text archive keeps
the original receipts and traces. Reconstruct the old fixture paths from that
map and verify each hash when reviewing an earlier binary. Private packet31
regeneration inputs, source/build receipts and samples remain ignored reference
evidence alongside the current KD inputs and captures.

The final cleanup archive retains 379 additional completed-run text records and
removed 366,000,424 bytes of regenerable/byte-verified duplicate scratch. Its
matching `scratch-cleanup-79f58b304243a3f5.json` carries the full restoration map.
Across both cleanups, 2,119,423,714 logical bytes were removed.
