# Retained analysis evidence

`route42-codegen.json` is approximately 1.2 MB. Retain it because it binds the
actual production adapter stages and the new four-stage candidate to their
final GEN blocks, branch structure, labels and instruction/message census.
The prior generic route_gather analysis is a different operation and cannot
substitute for this evidence. Restore it using `route42_offline.py` followed
by `route42_analyze.py` under the documented CPU constraints; the former
regenerates offline dumps and the latter verifies final ELF text and extracts
the block census. Source hashes and compressed assembly are retained beside it.

Compressed expert, tiny, extras, route and parallel assembly archives are
review evidence. The blind expert review intentionally retains its exact
input dumps independently of the author's annotation. Do not remove them as
apparent duplicates without preserving their hashes and updating consumers.

Ignored build executables, objects and SPIR-V are local coordinator inputs.
Build scripts and build receipts record how to restore them. Temporary IGC/AOT,
compiler and mock-window scratch is removed after evidence retention. No raw
output.bin larger than 20 MB is retained.
