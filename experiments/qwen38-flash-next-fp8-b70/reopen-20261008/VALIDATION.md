# CPU validation, 2026-10-08

No GPU use, server/container launch, pull/build, package install, credential
access, host setting change, Git branch, commit or non-manifest network request.
All new task files are in this directory. Concurrent LTX receipts are unrelated
and were left untouched. `CURRENT.md` and the certified result are unchanged.

Executed:

- AST/shell syntax checks on the new scripts.
- Both runner and client dry runs for MTP0, MTP1 and MTP3; all passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 test_cpu.py`: four checks passed,
  including insufficient-space refusal before any idle/GPU inspection and a
  mocked failing-client run that sends exactly one graceful server SIGINT.
- Protocol CPU mocked transport checks by the parallel reader: pin mismatch
  still completes sixteen diagnostic requests; nonzero cache count aborts at
  request five; cancellation aborts at request one and retains a summary.
  No real HTTP, server or telemetry process was used in these checks.
- Independent static review of V30 flag names, all 31 Python overlay paths,
  static MTP depth, shutdown, precision/cache policy and disk arithmetic.
  Fixed explicit allgather/reducescatter selection, per-arm graph shapes,
  model verification through preflight, client cleanup timeout handling and
  both word orders of the timed-out-job fault signature.

Not validated: Docker runtime imports/ABI, FP8 load/memory fit, actual selected
kernel/graph execution, measured speed, exact pins, clean GPU teardown, complete
process visibility, or full upstream PR history (the clone is shallow).
The packet is an executable **candidate with admission gates**, not a certified
working runtime. Disk is currently insufficient; complete passive process
visibility also needs to exist before execution. A no-password/no-sudo policy
is retained: scripts refuse missing access and do not change permissions.

Attribution: the selected Python deltas are wu1ff/Lumnus work pinned at
`9d79d28d7e32f33bdbd115c85d116583ce679cb6`, with individual file hashes in
`overlay-manifest.json`; native official V30/kernels retain upstream provenance.
The exact-token authority and benchmark clients are pre-existing lab work.
This packet is lab experiment preparation. No community boost is measured or
claimed. The repository-local
[review-model-contribution skill](../../../.agents/skills/review-model-contribution/SKILL.md)
governed this static review; runtime reproduction and promotion were not performed.
