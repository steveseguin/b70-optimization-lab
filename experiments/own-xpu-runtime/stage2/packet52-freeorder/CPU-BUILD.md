# CPU preparation and reproducible build

Run these serially from the repository on main. Every command has nice19,
the owner-approved CPU affinity and Python bytecode disabled. No command in
this file runs the device executable or initializes a GPU. The build tool
hash-verifies packet45's source/object closure and performs an identical
baseline relink before compiling the new packet translation unit. Existing
build trees remain read-only dependencies.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet52-freeorder
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind intel-host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py"
```

The CPU gate verifies every format/K and five orders in two fresh processes under each of GNU and Intel compilers, and
runs the production-shaped M1 control/candidate composition in two fresh
processes. Exact finite arithmetic, statuses, HC/attention epilogues, routed
weights and split scratch are checked. It reads no model weights and starts
no full-model oracle. CPU results do not replace E's native M2 and fresh GPU
byte gates. The build enforces serial compilation, an18GB free-space floor
and a1GB packet-build cap. Rebuilding changes the seal and invalidates earlier
device receipts; do not rebuild after coordinator qualification starts.
