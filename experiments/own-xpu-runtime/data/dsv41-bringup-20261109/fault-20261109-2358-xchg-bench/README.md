# GPU faults 2026-11-09 23:58:37 EST: our bench program, not the engine

- What: `xchg_bw_bench` (`engine/tools/bench/xchg_bw_bench.cpp`, first version) page-faulted on all six cards on
  its first kernel launch (`Fault response: Unsuccessful -EINVAL`, 8-49 lines per card, then `Timedout job` and an
  engine reset on each card's compute engine). Coredumps: `card*-devcoredump.txt.gz` (all name
  `xchg_bw_bench [134526]`, guc_id 3, the process's first job). Kernel lines: `kernel-log.txt`.
- Cause: the bench ran with `NEOReadDebugKeys=1 DisableIndirectAccess=1` (as the engine does) but its kernel
  read the six peer pointers from a by-value struct. With indirect access off, the driver makes only memory
  named by direct kernel arguments resident, so the loads through those pointers faulted. The engine passes
  every peer pointer as its own argument (`Backend41::xchg`, memory note on the driver's launch lock).
- Fix: the bench passes each peer pointer as a direct argument and picks among them with a select chain (no
  pointer array), and runs in the driver's default mode.
- Recovery: no reboot or reset. Queued engine runs stopped (one run was past loading and was ended by its unit
  stopping; no fault lines from it). Health probe `scripts/check-qwen36-xpu-xccl-health.sh` passed on all six
  cards (barrier + all-reduce, 2026-11-10 00:00 EST), kernel log clean after it; the fixed bench and the
  exchange test that followed ran clean.
