# Packet142 retention and restore

Keep this complete source tree, all inherited link objects, local vendor inputs,
negative logs, seals, allocation censuses, exact-byte transcripts, and proposals.
No original packet or historical record was modified. The copied history is under
`lineage-inputs`; its old paths are provenance, not current readiness pins.

Large files are intentional: `rope.bf16` (4 MiB) and `lineage-inputs/fusion-rope.hpp`
retain exact frozen rotary constants; copied vocabulary tables preserve the full
registered prompt inputs. The ~5.3 MB packet136 evidence bundle makes the submission
rehearsal independent of mutable parent chain folders. The ~54.4 MB
`lineage-inputs/legacy-fixtures.tar.gz` stores 80 inherited fixture/input files
(~202 MB uncompressed) whose build locations are ignored. Every member was rehashed
against the original copy before retaining the archive; member hashes are in
`legacy-fixtures.json`. These historical fixture bytes are needed to restore the
preserved aliases without depending on sibling source trees. This is the explicit
large-artifact retention justification. Nothing is a model weight download.

From the repository root, use the same CPU controls throughout:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet142-class-layout/restore_fixtures.py </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet142-class-layout/v5/qualify_cpu.py </dev/null
```

The source closure is tracked in `native-base`, with `build/checked` pointing
locally to it. `v5/build_engine.py` rebuilds the modified entry/parser through
`ops/compile_turn.py`; frozen parent object files must match `immutable-binaries.json`.
They are the explicitly allowed binary dependencies, not source dependencies.
Missing frozen binaries require their exact original reproduction; never replace
them by a merely similar current build. GNU and Intel compiler versions and commands
are recorded in `v5/engine-commands.json`/the build receipt. Build outputs remain
ignored, and regenerable own entry objects are removed after successful linking to
stay below 300 MB. The qualifier respects the compiler arbiter and timing holds.

The submission rehearsal is offline and disposable:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet142-class-layout/prepare_submission.py --evidence-bundle experiments/own-xpu-runtime/stage2/packet142-class-layout/lineage-inputs/packet136-chain-evidence.json.gz --rehearsal-parent packet136-record-bundle --output /tmp/packet142-submission-rehearsal.json </dev/null
```

Choose a fresh output path. It replays the parent's identity and score, checks the
attestation/payload, refuses a corrupted hash, and never submits or creates a new
packet142 performance claim. The retained successful receipt is a CPU-seal input.
Generated shape archives preserve every original member byte and are bound by the
CPU seal. Requalification changes evidence and requires a new final readiness marker;
do not silently reuse an old marker after editing sources.
