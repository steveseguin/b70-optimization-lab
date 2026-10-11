# Third-incident acceptance repin — 2026-10-11

Commit `597817eb0a` pinned the October 11 owner receipt in `screen.py`, leaving
October 10 test clocks and the controller's overlay support hash stale.
Updated acceptance and probe fixture clocks to 00:36:14 acceptance / 01:00 UTC
current time, including the first-forward mounted-package fixture. Synthetic
health fixtures now follow acceptance; historical health receipts are unchanged.
Fault-at-boundary, later-fault, stale-health and pre-acceptance-health refusals
remain tested.

Copied current `screen.py` into the teardown bundle and used its existing
`build_patch.py` generator to reseal the copied manifest, patch and patch manifest.
The generated manifest replaces the live manifest; its only change is the
`support_files.screen.py` hash. Runtime/teardown payloads and live controller
code are unchanged. The bundle retains its frozen preimage commit; earlier
review evidence describes the earlier bundle, not this revision.

- `support_files.screen.py`: `fdb57ed3241aeb29e3d1060671fe0e8ae0feebf2d06a80e316039d975d3f1428`
- `overlay-manifest.json`: `daf50d2391549a9fb5c03ee2cf3a69e763cc44e621fdaf35e4b06529c7142b69`

## CPU checks

[Logs and receipts](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/acceptance-repin-20261011/)
include initial first-forward fixture failures and final reruns. All processes
used nice 19 and OMP/MKL/OpenBLAS thread limits of 2. No GPU, server, container,
systemd or port 8188 operation occurred. Owned temporary scratch was removed.

| Suite | Passed | Skipped | Failed | Total |
| --- | ---: | ---: | ---: | ---: |
| Lane | 227 | 6 | 0 | 233 |
| Combined probes | 84 | 1 | 0 | 85 |
| Teardown | 49 | 0 | 0 | 49 |
| Historical host-pointer candidate | 8 | 0 | 1 | 9 |
| First-forward rerun (already in probes) | 37 | 0 | 0 | 37 |

Unique total: **368 passed, 7 skipped, 1 failed, no errors (376 tests)**.
The documented restricted runner excludes five XPU worker rehearsals, one
real-checkpoint check and one fatal-SIGALRM probe. The remaining failure is
`test_addressing.AddressingTests.test_source_pins_and_exact_patch`: the historical
`overlay-fix-hostptr/explicit-host-pointer.patch` differs from a diff against
today's overlay. Its inputs and candidate patch were not changed by this repair;
no candidate was rebased or silently qualified.

From the repository root, with `p=experiments/qwen38-flash-next-fp8-b70/reopen-20261008`:

```sh
nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B "$p/overlay-fix-teardown/run_cpu_tests.py" lane
# Run probe, teardown and first-forward with the same limits and python3.
# Probe discovery uses its own directory, resolving container_command correctly.
nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B -m unittest discover -s "$p/overlay-fix-hostptr" -p 'test_*.py' -v
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$p/overlay-fix-teardown/build_patch.py" --check
```

The requested attempt-8 `preflight --mode calibrate-load --loading-ram-guard-gb 96
--dry-run` exited **0**, with no `REFUSED/STOPPED` line. Expected capacity
`REFUSE` diagnostics remain. The [full dry-run output](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/acceptance-repin-20261011/dry-run.log)
ends with the diagnostic-mode message, the no-operations statement and two
printed commands; neither command was executed. Builder verification and
`git diff --check` pass.

Dry-run does not call live journal/health admission. The supplied health receipt
starts **00:03:55 UTC**, before acceptance at **00:36:14 UTC**, so this preview
cannot qualify it for a real launch. A later valid health receipt is still
required; this task did not generate one or weaken the gate.


## Engine-window outcome: fourth incident, 2026-10-11

The coordinator obtained later passing health at **00:43:22–00:43:28 UTC** and
ran attempt 8 under the repinned manifest. The 00:45:38 payload verification
passed; all ranks loaded. At **00:56:50 UTC**, all four cards faulted during
startup profiling; the controller sent one SIGINT and the container exited 1
at **00:58:47.411366 UTC**. The coordinator recorded the fourth-incident halt.
Saved postflight at **00:59:35–00:59:42** passed with no new fault lines; this
does not reopen the window. [Full outcome and retained evidence](2026-10-11-attempt8-fourth-incident.md).

The original `fault-archive-20261011T003614Z-owner-accept-receipt.json` is
unchanged (SHA256 `c2947a5065aeb27bd88938ed09cb8801043646e2e4d8f5e433ff8da7807ba2f0`).
Its third-incident acceptance was used for this window; its halt-on-further-fault
condition now applies. This appended outcome grants no new authorization.
LTX stays off. The owner decides recovery; recommend an authorized reboot
before further GPU work. No recovery action was taken by this CPU review.
