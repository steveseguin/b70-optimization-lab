# Qwen3.8 Flash-Next TP4 MTP0 A32 M1-only retry preregistration

Date: 2026-08-31
Status: frozen isolated retry after the A31 client-binding negative

## Scope

A32 retries A31 as attempt 32 on port 19704. Model, revision, current vLLM
source, sealed kernel stage, synchronous PLE-only eager runtime, MTP0, M1 key-1
warps-8 tuned configuration, memory/cache settings, requests, quality gates,
performance selectors, and protected-result policy are identical to A31.

A31 reached a healthy endpoint but its client rejected the generated inner
supervisor because that process command line does not contain the tracked outer
script name. No inference request ran. A32 changes only this binding contract.
The client reads `/tmp/q38-mtp0-ple-only-a32.pid`, requires that inner process,
extracts exactly one exported outer-supervisor PID and start-time from its
environment, and verifies the live outer A32 script identity, start-time, and
host plus GPU0-3 lock descriptors.

## Isolation and lifecycle

Attempt 32 uses new state, run, cache, compile, RPC, inner-supervisor evidence,
and outer-lifecycle paths. No A31 artifact may be reused or overwritten. The
unchanged outer lifecycle remains the sole runtime entrypoint and retains
fail-closed source hashes, host/resource admission, exact four-card preflight
and postflight, bounded journal evidence, full teardown, recovery floors, and
the final evidence manifest.

The inherited semantic boundary, 16 exact repeats, three protected short
hashes, cache-zero 4K needle, and two exact-4K authority rows remain mandatory.
`same_boot_output_repeat` remains a within-run quality field, not a boot rule.
No reboot is required. Any miss is a bounded negative and leaves protected
results unchanged.

Structured preregistration:
[`20260831-tp4-mtp0-a32-moe-m1-current-prereg.json`](../data/20260831-tp4-mtp0-a32-moe-m1-current-prereg.json).
