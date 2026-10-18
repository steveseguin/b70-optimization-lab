# Packet129 retention

The native source is a packet124c copy with preserved symlinks. `parent-manifest.json`
and `prepare129.py` identify the source and initial delta. Every reused target
object is hash-bound by `evidence/object-identity.json`; rebuild those objects
through their original packet build instructions before rebuilding this entry.
No foreign engine code or downloaded weights are used.

`build/` contains regenerable mirrors, object files, CPU fixtures and binaries;
it is ignored, capped at 300 MB and not device evidence. `engine-commands.json`
records exact compile/link commands. Device compilation does not run a GPU.
The one-load device output belongs only in `evidence/device-B`, once admitted.
Keep raw target, production and shadow rows, model identities and result hashes.

Inherited helper/receipt copies unrelated to this diagnostic were omitted from
the new tree; their original bytes remain untouched in packet124c. Inherited
native source and data remain exact where required by the compiled closure.
All tracked artifacts at least 1 MiB are listed in the final audit with a
source/restoration rationale. This packet removes no existing evidence.

`rope.bf16` is 4,194,304 bytes. It is the inherited exact rotary constant table,
needed by the compiled runtime and CPU startup fixtures. Restore it byte-for-byte
from `../packet124c-record-bundle/rope.bf16` and verify the hash in the build
receipt; do not regenerate it with different math.
