# Qwen3.8 Flash-Next health-gated boot reuse policy

Date: 2026-08-31
Status: active; supersedes the experimental one-load/one-experiment-per-boot rule

The Qwen3.8 Flash-Next lane no longer consumes a boot after an experiment or a
full model load. Boot identifiers remain in evidence for provenance only; they
must not decide whether a later experiment may run.

Admission now depends on the state that matters:

- exclusive host and device locks;
- an unused, no-clobber evidence path;
- no conflicting model process, listener, or device owner;
- exact model, source, runtime, patch, launcher, and storage identity;
- sufficient host memory, swap, shared memory, and storage;
- the applicable bounded four-B70 discovery and compute/free-memory preflight.

Every accelerator run must clean up and execute its bounded host, four-card,
and kernel-journal postflight even when its experiment gate fails. A later run
may proceed on the same boot after a clean close and a new successful
preflight. If cleanup or postflight cannot establish health, later accelerator
work is blocked until a bounded recovery check succeeds. A reboot is a
last-resort recovery operation, not routine experiment isolation.

Historical packets and their recorded boot IDs remain unchanged evidence of
what was preregistered and executed at the time. This policy supersedes their
boot-consumption language for current and future scheduling; it does not alter
their measurements or interpretations.
