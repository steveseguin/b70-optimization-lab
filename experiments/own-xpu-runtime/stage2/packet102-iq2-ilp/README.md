# Packet102 IQ2 ILP

[Task note](../../../../notes/2026-10-18-own-runtime-packet102.md),
[preregistration](PREREGISTRATION.md), and
[boundaries](DO-NOT-REPEAT.md).

CPU preparation is complete. The coordinator independently ran the early
microbenchmark proposal while CPU gates finished: **no candidate passed the
15% gate**. [Micro closeout](MICRO-CLOSEOUT.md). This task launched no GPU work.
Build: `build_microbench.py`, then `build_engine.py`, `cpu_gate.py`,
`inspect_registers.py`, `lookup_proof.py`, `full_shape.py`, `memory_plans.py`,
`startup_import_gate.py`, `python_gate.py`, `seal.py`, `propose_jobs.py`,
`queue_plan.py`, `final_check.py`.
Use `nice -n 19 taskset -c 8-15,24-31 python3 -B` and stdin `/dev/null`.

Three spill-free micro candidates remain: batch2, batch4, and shared input.
The two combinations are [closed before device work](COMBINED-CLOSEOUT.md).
Run `lookup_proof.py` after `inspect_registers.py`; it checks all linked grid
send batches and the reduced activation-load count.
