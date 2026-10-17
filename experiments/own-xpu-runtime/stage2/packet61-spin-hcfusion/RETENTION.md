# Packet61 retention

The ignored build is about 143 MB logically and 108 MiB allocated, below the
400 MB limit. Unchanged objects are hardlinked from packet60; parent fixture
binaries and inputs are read-only symlinks. Never write through those links.
RoPE and the oracle are links to the sealed packet56/packet49 inputs.

Keep the two engine binaries, controller binaries, generated checked inputs,
link objects, commands and CPU outputs for screen/chain verification. The
build receipt binds the actual reused objects and both generated/source header
closures. `engine-commands.json` records every new compile and link command.
The packet60 build receipt records the unchanged objects' original commands.
External compiler inputs are retained by hash under
`evidence/inherited-build-inputs/`; no new model payload is copied.

Before sealing a fresh preparation, with parent56, packet56w and packet60
inputs/objects restored and verified, the CPU build and gate commands are:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_engine.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
```

They refuse an existing screen seal. Do not remove the seal to rebuild a tested
candidate. If ignored inputs are reclaimed later, restore exact retained bytes
or prepare a separate candidate and seal; do not mutate any sealed parent.
The generated `build/fusion-rope.hpp` is the unchanged packet56w input link.
Legacy CMake/helper files retain their historical purposes; only the lean
builder above defines this packet's compiled engine.

The CPU byte fixtures are small tracked evidence. This packet is a lab
candidate with local retained-build dependencies, not a public clean-build
release or a published model package.
