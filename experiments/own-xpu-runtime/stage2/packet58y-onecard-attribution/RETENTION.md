# Packet58yb retained source evidence

`lineage-inputs/frozen-source-inputs.tar.gz` (about 3.8 MiB) is required to
retain the exact historical compiler/source provenance while removing live
sibling source and receipt dependencies. It contains no model weights or
secrets. `lineage-inputs/member-hashes.json` gives every original member hash;
`source-relocations.json` seals the archive and manifest. Every member was
extracted in memory and rehashed against its original before the temporary
expanded copies were removed. The original sibling trees were untouched.
Restore any member with Python tarfile.extractfile or tar -xOf; verify its
SHA256 against the member manifest. Do not execute historical launch code.

`lineage-inputs/original/` contains byte-identical historical memory-admission,
fixture and library-path receipts/source files. Their consumers now point to
these copies. `lineage/pre-58yb-*` preserves earlier seals and metadata, including
the readiness marker and unchanged numerical CPU evidence before path relocation.
The 18:42 pre-device refusal remains historical; no native job ran in this repair.

`lineage-inputs/memory-admission-inputs.tar.gz` (about 1.4 MiB) preserves
all original host-memory samples, allocation metadata and source receipts used
to derive the unchanged admission bounds. Its member-hash manifest is local.
Every member was rehashed; `host-admission/derive.py --check` reconstructs a
bounded temporary metadata tree from this archive and reproduces all profiles
and 29 historical windows exactly. It reads no model tensors. The archive
avoids thousands of duplicate metadata lines while keeping the original bytes.
The 19 replay/refusal tests now use these local inputs. No original sibling
file was removed. The relocated 58c supervisor receipt also retains its exact
original bytes under `lineage-inputs/58c-supervisor/`.
