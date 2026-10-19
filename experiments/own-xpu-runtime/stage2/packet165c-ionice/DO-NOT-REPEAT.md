# Packet165c launch regression

- Never launch the one-card model reader without `ionice -c3`; checking argv
  alone is insufficient. Assert the kernel I/O class in an intercepted exec.
- Proposal renaming invalidates READY proposal hashes. Keep readiness false
  while updating pins; write final READY only after real plans and reports pass.
- CPU marker reset/sensor tests are orchestration evidence, not device quality
  or performance measurements.
