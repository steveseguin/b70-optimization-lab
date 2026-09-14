# Guarded diagnostic v2 — first native attempt safely refused

This successor adds two hardenings to the earlier guarded harness. It does not rerun the failed experiment or qualify compiled C++ output. The failed `test_block_cpu.py`, earlier `test_block_cpu_guarded.py`, earlier `accelerator_guard.py`, and their receipts remain unchanged.

- `test_block_cpu_guarded_v2.py` writes exclusive `startup-identity.json` immediately after creating its evidence directory and **before Torch import**. It records PID/PPID, UTC timestamp, command, source/helper/qualification identity, unchanged options, and the process-local compiler environment. It flushes and fsyncs the file before proceeding and pins the receipt in the final report. An existing file or symlink cannot be overwritten; writing after Torch import is rejected.
- `accelerator_guard_v2.py` marks every trapped accelerator entry as permanently failed. Explicit checks run after trap installation/imports, before and after each model call, and before final graph review. Finalization cannot preserve `passed=true` after a recorded trap, even if upstream code catches `BaseException`. Reinstalling the guard cannot clear that state. The trap still never calls the original accelerator entry.

`guarded-diagnostic-v2.patch` records both exact source deltas; `guarded-v2-source-delta.json` pins parent/successor files. The whole-harness AST reverses to the earlier guarded harness after removing only the new receipt/failure checks and intentional helper-name/doc changes. Fixture arithmetic, compiler options, stage schedule, parameter identity gates, graph counts and byte-parity checks are unchanged.

`guarded-v2-stdlib-01.json` reports **14 passed stdlib tests**, including 31 trapped entry points tested with fake modules, sticky failure after an explicitly swallowed exception, startup-file persistence and exclusivity, source ordering, unchanged parent hashes, and whole-harness AST reversal. No Torch, Kitchen or Inductor module was imported by the tests. Only temporary stdlib test files and this explicit test receipt were written.

Reproduce the source/fake tests using a new receipt path:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python experiments/ltx25-b70/native-cpp-block-01/test_guarded_v2_stdlib.py --output /absolute/new-guard-tests.json
```

**The stdlib tests qualify the guard behavior, not compiled C++ output.** Root subsequently ran exactly one guarded native diagnostic on 2026-09-14, PID91112, and it exited1 after blocking `torch.xpu.device_count` during Comfy Kitchen Triton registration. Startup identity was persisted before Torch import; XPU and CUDA remained uninitialized at exit, and no model/compiled calls occurred. It **did not reach the original CPU cache-metadata hypothesis**. Parent postflight found the same idle server as the only render-node owner and no fault evidence. See [guarded-v2-native-attempt-01.md](guarded-v2-native-attempt-01.md) and its linked receipts.

There was no retry, compilation, availability simulation or live service change. Further native work remains unscheduled until the confirmation campaign is finished. The API guard is not an operating-system sandbox and does not implement a CPU-only replacement for Inductor's Triton metadata query. The earlier preparation/source-delta receipts remain immutable historical records; this section records the later attempt.
