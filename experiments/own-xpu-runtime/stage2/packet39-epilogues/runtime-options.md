# Offline and runtime compilation boundary

No device discovery, device program or GPU measurement ran during preparation.
`build_native.py` compiles and links with the same precise flags, including
`-fno-fast-math`, `-ffp-contract=off`, IEEE denormals and precise device divide/sqrt.
K0 and G4 are byte-identical executables: K0 selects `--compile-smoke` inside the
same binary and builds its executable kernel bundles without kernel submission.

`offline.py` selects only SPIR-V whose entire bytes occur in the shipped native
binary. It invokes the installed offline compiler for PCI ID `0xe223`, revision
0, with `-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt`. The exact commands,
SPIR-V hashes and binary offsets are in `candidate-modules.json`. The disassembly
must match the final offline ELF text, including zero padding, before the static
gate accepts it. The archive in `offline-retention.json` preserves those bytes.

This is offline evidence for that compiler/target/options, not a claim that a
future runtime driver will emit identical assembly. Runtime environment and
libraries are recorded by the window wrapper and must match between K0 and G4.
A changed compiler, stepping, driver or precision option needs renewed assembly
review. Device byte identity is still mandatory in G4; its 84 prospective checks
have not run. G4 is one-card screening and cannot establish a full-model speed
verdict or replace the model oracle and fresh-window repeat.
