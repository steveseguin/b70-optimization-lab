# Retained inputs and evidence

`packet71-copy.json` hashes the frozen tracked packet71b files before copying.
Its inherited `packet68c-import.json`, transaction fixtures, earlier build/seal
attempts and milestone receipts remain historical evidence, not new 71c passes.
Parent seals were moved into `milestones/packet71b/` in this new copy only.
The current build receipt and root seals bind packet71c's actual sources.

New CPU evidence is `fixture/m2-receipt.json`, `evidence/unfused.json`,
`evidence/fullshape.json`, current compiler fixture logs, metadata/import gates,
wrapper tests, direct plans and queue plans. Full-shape allocation censuses and
test-only generated native sources are in ignored `build/fullshape/`; the gate
records their source identities and can regenerate them without model reads.

The 4 MiB `rope.bf16` is a pinned target constant required at build/runtime.
Restore its exact bytes from packet71b and check the copy manifest. The four
3.1 MiB `fixture/{gnu-host,intel-host}-{expected,actual}.bin` files retain actual
independent output bytes for both compilers. Consumers are `fixture/m2-receipt.json`
and both screen seals. Restore with `build_engine.py` and `batch_cpu_gate.py`;
all four hashes must agree with the receipts. The smaller new
`*-unfused-{expected,actual}.bin` streams come from `unfused_gate.py` and are bound
in both seals. Evidence size or duplication does not authorize deletion.

The build reuses hash-checked, unchanged packet64 objects. Build objects,
checked-source mirrors and binaries remain ignored; recorded commands and
hashes permit originating-host reconstruction. No weights, secrets or host
caches are copied. Preparation added only this bounded packet. The root disk
was already below CURRENT's general 50 GiB reserve (about 25 GiB available);
no cleanup or bulk/model writes were attempted. The packet's inherited build
checks retain their 12 GiB floor and 1 GB build cap. Device storage admission
remains the coordinator's existing independent gate.
