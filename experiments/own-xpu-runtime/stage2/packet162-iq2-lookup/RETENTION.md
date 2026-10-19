# Packet162 retention and replay

Track the generated integer decoders, private kernel source copies, generator,
CPU harness/build/audit scripts, final receipts and initial failure logs. No
tracked artifact is 1 MiB. All are source or compact research evidence, with
no model data or secrets. Existing packet trees are unchanged.

`build/` is ignored local CPU compiler output, retained in place. Rebuild it
with the commands and limits in [CPU-MICRO.md](CPU-MICRO.md). The final
`evidence/cpu-proof.json` binds both compiler commands, binaries and complete
repository dependency closure. This is the replay authority; earlier logs
capture development failures but their old executables were superseded locally
and are not claimed as independently replayable build identities.

`analyze.py` deterministically regenerates `logic_grid.hpp`, `candidate.hpp`,
`enum_grid.hpp`, `enum_candidate.hpp` and analysis.json. Those candidates are
private textual derivatives of the pinned production E1 header. They are
retained as rejected/ungated research, never applied to the shared runtime.
The enum table `encode` is a CPU preparation map of grid identities, not model
weights. The generated decoder itself uses integer unranking.

The initial and second receipts remain under `evidence/logic-attempt1/` and
`evidence/attempt2/`. They are superseded by the final actual-native plus
raw-chain check, not deleted or silently presented as passes. No device
binary, device evidence, performance curve or public recipe exists here.
