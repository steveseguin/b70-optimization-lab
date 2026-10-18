# Retention and reconstruction

The build is 181.4 MB logical, below the owner's 1.2 GB cap. Build processes have
an 8 GiB address-space limit; the main build's maximum child RSS was 709.4 MiB.
All commands ran at nice 19 on CPUs 8-15,24-31 with Python -B and stdin /dev/null.
Compilers ran serially and were started after checking the existing compilers.
No GPU, service, sudo, power/memory/swap/cache change or reboot was used.

`build/` and selection binary links are ignored generated artifacts, retained
locally. The initial checkpoint included generated build files; the final
milestone removes them from the index without deleting their bytes. Their
hashes remain in receipts. Keep the parent packet75 objects and source closure;
this incremental lab build is not a standalone public release.

The 4 MiB `rope.bf16` is an exact copied runtime input, needed by the packet-local
load path. Restore its original bytes from packet75, then verify against
`parent-source-manifest.json`; it is deliberately tracked despite its size.
The parent manifest pins all copied sources. `rank0-prefix.patch` is the only
runtime source delta. `dependency-pins.json` pins the unchanged shared wrapper.

For reconstruction into this packet's original path, with no sealed candidate
in use, restore ignored artifacts from retained originals or rerun serially:
`build_engine.py`, `composed_cpu.py`, `full_shape.py`, `memory_census.py`,
`cpu_gate.py` (with OMP_NUM_THREADS=2), `protocol_gate.py`, then `seal.py` in a
fresh reconstruction. Existing receipts/seals must be retained, not overwritten.
The full-shape helper generates only payload-elided mock sources and virtual
device addresses; it reads the real tensor shape plan and does not load weights.

Run `test_packet79.py`, the 69 shared wrapper tests named in `final_check.py`,
`queue_plan.py`, then `final_check.py`. The reconstructed packet must reproduce
all source, kernel object, fixture, census, admission and seal bindings before
any coordinator launch. Build paths are fixed in generated include mirrors;
copying binaries alone is insufficient. Failures and final passing evidence
are retained under `evidence/`. Device output identity and speed are not CPU claims.
