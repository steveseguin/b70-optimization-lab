# Retention and rebuild

Preserve this packet's source, exact selection, dependency/source pins, focused
instrumentation patch, build commands/receipt, CPU gate evidence, sealed view
and proposed queue line. Preserve every later raw control/attribution receipt,
event file, kernel log and teardown/fault record. Failed reports are repairable
from raw files and must not trigger deletion or automatic reruns.

The ignored `build/` contains approximately 135 MB of local objects, executables,
checked-source mirrors, tiny CPU fixtures and full-shape mock outputs. These are
originating-host experimental artifacts, not a publicly reproducible release.
The binaries and inherited object inputs are bound by `build-device-receipt.json`
and `evidence/object-identity.json`; do not claim fresh device qualification from
CPU equality. The model payloads are never included or read by these CPU gates.
`rope.bf16` references the identical frozen packet70 table rather than adding
another 4 MiB copy to Git.

For a deliberate fresh rebuild, preserve the existing build and seal first.
`build_engine.py` recreates the checked include mirror and compiles/links one
entry translation unit per mode, using packet65's exact retained link inputs.
It refuses an existing build receipt. Run serially with no other compiler,
`OMP_NUM_THREADS=2`, nice 19, cores `8-15,24-31`, `python3 -B`, stdin `/dev/null`.
The builder sets a 6 GiB address-space cap. Then run `cpu_gate.py`,
`fullshape_gate.py`, `reset_gate.py`, the packet/shared Python tests, and `seal.py`
on a fresh selection destination. `seal.py` never overwrites an existing seal.
Do not reseal a dependency mismatch silently: compare the recorded source and
binary identities, then prepare a new reviewed view and evidence.

`report_fixture_gate.py` uses hardlinked historical packet69 events and temporary
synthetic receipt identities solely to test the report. It deletes only its own
temporary fixture and saves no historical timing as a packet77 result.
The final CPU check and queue planner write only packet77 evidence or a temporary
queue. Frozen parent sources and live queues stay unchanged.
