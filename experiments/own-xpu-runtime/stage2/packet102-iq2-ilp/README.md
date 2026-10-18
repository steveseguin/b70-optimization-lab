# Packet102 IQ2 ILP

[Task note](../../../../notes/2026-10-18-own-runtime-packet102.md),
[preregistration](PREREGISTRATION.md), and
[boundaries](DO-NOT-REPEAT.md).

CPU preparation only. The first delivered proposal is the full-shape device
microbenchmark; future device execution belongs to the coordinator.
Build: `build_microbench.py`, then `build_engine.py`, `cpu_gate.py`,
`inspect_registers.py`, `full_shape.py`, `memory_plans.py`, `python_gate.py`,
`seal.py`, `propose_jobs.py`, `queue_plan.py`.
Use `nice -n 19 taskset -c 8-15,24-31 python3 -B` and stdin `/dev/null`.
