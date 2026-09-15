# Packet12 builder source review

2026-09-14. **No source-admission or proof-closure blocker found.** Nine
focused stdlib tests passed using the actual passed CPU lifecycle receipt and
frozen packet11 checker source. The independent reviewer did not prepare a
packet, call runtime checks/endpoints, import Torch/Comfy, or perform device or
process actions. Parent root owns offline packet construction and native work.

Reviewed builder SHA256:
`70f6dc399218477ef8ade0058ddaff31c5efdc35c9c2592b21b89c99c703ffc6`.
Parent11 manifest: `34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08`.
Actual CPU lifecycle result: `c9c2d81db33ab5d3174aaaaa87a31c6cf03e5d7923f1b9c305bae554e51ea452`.

The v2 schema preserves the historical packet11 host admission separately.
Its old resident hash now resolves to the archived resident bytes; current
residentv2 and memory-helper hashes resolve to the new six-case CPU proof.
The generated checker retains the complete earlier ancestry, graph checks,
model receipt/fault guard and source-pin checks. Its changes reverse to the
frozen parent checker byte for byte. Every parent11 file is checked against
its original hash, at its current location or one of the three explicit
archived paths. Numerical sources, graphs and launcher remain inherited.

New evidence closes over the actual CPU result, startup identity, fixture
evidence, driver and helpers. Current host metadata is frozen as a generated
literal; it does not claim full-model or speed qualification. The builder
validates all inputs before creating packet12, refuses an existing output,
marks construction incomplete until verification, and rechecks parent/proof
bytes before completion. Check-only returns before packet-writing operations.

The [new test](../scripts/test-host-transition-builder-stdlib.py) checks the
actual pass and 23 invalid admission fields, all five qualified implementation
pins, missing/duplicate checker replacement contexts, v1 schema refusal,
unchanged inherited checker functions, all transition proof bytes, current
and historical metadata, inherited graph/source/launcher hashes, and all three
archived changed-parent paths. The generated transition tail executes against
in-memory files. This isolates its proof-closure behavior; it is not a mock
claim that the complete built packet passed `verify_packet`.

Command: `python3 experiments/ltx25-b70/scripts/test-host-transition-builder-stdlib.py`.
Exit0; nine tests; no failures/errors; Torch absent. [Result](../data/host-transition-builder-stdlib-01.json).
The [test snapshot patch](../patches/host-transition-builder-stdlib-01.patch)
preserves the exact reviewed test. Full packet verification remains root's
separate build check. Initial full-model assembly still needs the separately
reviewed cold-RAM admission; CPU lifecycle proof does not establish that peak,
full-model XPU release/residency, complete-clip byte parity or speed.
