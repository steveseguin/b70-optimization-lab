# Laguna production first-live readiness canary

Date: 2026-08-03 America/Toronto

Status: **production-only, default-off orchestration implemented and CPU-tested;
no service, model, endpoint, XPU, or performance run was performed**.

## Product problem

The protected graph service lazily captures its target verifier on the first
eligible live request. Prior evidence measured `10.478 s` of graph capture
inside a `14.32 s` first generation. That is valid and deliberately retained
for cold benchmark claims, but it is poor production behavior: the first real
user pays a one-time implementation detail after `/health` has already begun
returning success.

The production policy is now separable from measurement policy. Cold runners
remain byte-for-byte free of this canary. A production orchestrator may arm
`LAGUNA_PRODUCTION_READINESS_CANARY=1`, keep the backend loopback-only, and run
`tools/run_laguna_production_readiness_canary.sh`. The orchestrator must expose
the LAN frontdoor only after the script atomically publishes
`production-ready.json`.

This does not reduce total startup work. It moves the known first-live cost
from first-user latency into startup-to-ready time and proves that the warmed
process is the intended one before traffic reaches it.

## Fail-closed sequence

The gate performs these steps in order:

1. wait for loopback `/health`;
2. require four diagonal TP4/EP4 worker selector records with live PID/start
   identities;
3. bind all four workers to exactly one expected grouped-GEMM DSO by resolved
   path, device/inode identity, and SHA-256;
4. require the latency-successor worker contract, including
   `VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS=1`;
5. issue one fixed, non-scored 400-token `python-lru-cache` request;
6. require the exact canonical q1 400-token prefix, prompt identity,
   `cached_tokens=0`, and request-local speculative counter consistency;
7. require 11 draft tokens per cycle, a positive non-flat decaying acceptance
   curve, and the per-position acceptance sum to equal the accepted total;
8. require target capture/replay `146/145` and draft capture/replay `14/13` on
   every rank, rejecting any unexpected audited topology; and
9. atomically publish a readiness marker containing hashes of the canary and
   worker evidence.

The raw response and request-local counter delta are persisted before any
assertion can fail. An unsuccessful run leaves no readiness marker. The
orchestrator remains responsible for stopping the unadvertised backend on
failure; the canary does not accept or guess a process group to kill.

## Source identities and validation

The latency successor is:

```text
/home/steve/src/laguna-vllm-e2e-latency-integration-20260803
experiment/laguna-e2e-latency-integration-20260803
d9e7e2f1a xpu: attest Laguna exact prefill at worker startup
```

The new v2 worker contract adds the exact-prefill selector without weakening
the old frozen v1 validator. The main-repo validator selects v2 only with
`--require-exact-prefill`; old evidence and runners keep the v1 default.

Offline validation passed:

- 77 combined vLLM tile, prefill, and worker-evidence tests;
- 33 main-repo readiness, smoke, and worker-evidence tests plus 48 subtests;
- Ruff lint and formatting for changed Python;
- Bash syntax validation; and
- whitespace checks.

`shellcheck` is not installed on this host, so no shellcheck result is claimed.

## Boundaries

The canary is not a benchmark result, throughput optimization, or new record.
It must never be invoked by the cold measurement legs, and a process warmed by
it must never be described as cold. Prefix caching remains disabled; only
code/graph state is intentionally warmed. The protected conventional short
decode result remains `125.4619731637751 tok/s`.

The NVMe/device quarantine remains controlling. This implementation grants no
authorization to start a service, load a model, contact an endpoint, run an
XPU probe, alter swap, reset, reboot, or perform recovery.
