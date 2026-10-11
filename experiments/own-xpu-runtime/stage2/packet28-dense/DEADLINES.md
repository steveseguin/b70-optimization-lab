# Packet28 budgets

Expected durations are planning estimates only, never hard cutoffs or speed evidence.
K0:30s work +17s first JIT =47s expected,300s watchdog.
G2:400s work +2×17s JIT =434s expected, minimum/default1736s watchdog (4×434).
The owner may select a larger watchdog up to7200s. The native wait is300s for any
submission, accommodating first-use compilation; the planning GPU execution allowance
is10ms per launch group for all classes, exceeding4× the measured logits maximum
of about2.2ms. The10ms allowance is not an enforced deadline. The actual per-submission completion
budget is300s; no GPU command is killed to enforce a performance expectation.

Before creating or checking a fault latch the wrapper runs ldd and requires every
library resolved. It checks build/source hashes, a closed environment allowlist,
K0 identity (boot/card/binary/environment/build) and the kernel journal cursor.
It launches each owner exactly once in a systemd user unit with Restart=no.

On a fault, signal, journal failure or watchdog expiry: write the failure before
SIGTERM, allow a60s cooperative drain, then retain a still-running owner for the
coordinator. Never hard-kill, reset, reboot, or retry. A candidate numerical mismatch
is recorded and excluded; it is not a reason to terminate other safe candidate tests.
