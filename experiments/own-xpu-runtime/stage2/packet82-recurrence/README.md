# Packet82 recurrence

Two exact-order recurrence candidates on copied packet75 engine sources:
`rec-gates` gives decay and beta to separate waiting subgroups;
`rec-parallel` also separates Q and K normalization. `production` means the
record configuration's `rows4-shared`. All use WG128 / SG32, 1,536 groups,
BF16 state, FP32 intermediates, the same trees and per-token BF16 rounding.
No extra launch, scratch allocation, state layout or precision change.

[Analysis](ANALYSIS.md) was committed first. [Window and proposed jobs](WINDOW.md)
use the unchanged shared v4-lanes wrapper. [CPU closeout](CPU-PREPARATION-CLOSEOUT.md)
records validation and open device gates. Do not use the copied historical
chain helpers as a registered packet82 chain: this packet registers screens
only through `run_screens.py` and its three sealed views.

Build and gate order (all CPU only; nice19, CPUs8–15/24–31, stdin /dev/null):
`build_engine.py`, `cpu_gate.py`, `full_shape.py`, `python_gate.py`, `seal.py`,
`final_check.py`, `queue_plan.py`. Only one compiler may run at a time.
Each script uses python3 -B. `inspect_registers.py production|candidate`
provides offline BMG-G31 diagnostics; it never opens a device.

The incremental build reuses hash-verified packet75 objects and recompiles
entry-main and p49d_submit, then relinks both GNU-host and Intel-device binaries.
The engine source comes from packet75; preparation scaffolding is adapted
from packet81, with both origins recorded in parent-source-manifest.json.
