# Packet 42 deadlines and stop rules

Only the coordinator runs device windows. CPU preparation runs no device benchmark binary,
no device discovery and no driver operation.

| Window | Estimated duration (unmeasured) | Wrapper watchdog |
|---|---:|---:|
| K0: build every linked image in every executable | 120 seconds | 480 seconds |
| T1: 1,180 launch-floor rows | 600 seconds | 2,400 seconds |
| K2: expert, dense, route, recurrence and tiny cases | 600 seconds | 2,400 seconds |

Expected times are reporting estimates, never early deadlines. Each watchdog is
at least four times the estimate and at least 300 seconds. At expiry, record
failure first and request cooperative SIGTERM once. Never retry or hard-kill.
If the process remains after 300 seconds, retain it and report its PID for the
coordinator. Do not start another component after a fault or infrastructure
failure. An ordinary candidate validation/byte failure becomes a failed row;
other cases continue.

The wrapper reads a journal cursor immediately before its first child. Only
new specific GPU fault lines after that cursor may create FAULT.json. Old
reviewed lines, admission refusal, loader failure, receipt formatting and
ENOSPC are not GPU faults. A receipt write failure is printed immediately to
stderr and returns failure; atomic writes do not leave empty success records.

All commands run nice19/idle IO with OMP_NUM_THREADS=2 and inherited affinity.
The wrapper refuses under 8 GB root free space or above 8 GB child anonymous
memory. No power, memory, swap, cache, driver or reboot changes. No sudo.
