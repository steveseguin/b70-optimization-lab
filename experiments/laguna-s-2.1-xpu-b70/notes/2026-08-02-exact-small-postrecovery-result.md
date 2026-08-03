# Laguna exact-small post-recovery smoke result

Date: 2026-08-02 America/Toronto

Status: **INCONCLUSIVE — stopped by the frozen host-memory guard before API
health, graph capture, or any request. The one-shot authorization is consumed.**

The corrected 49-argument harness and its separate execution lock were
committed as `5637e3e33` and `7ff670b9a`. All 10 CPU harness tests then passed,
along with 14/14 kernel static contracts and 3/3 focused vLLM integration
tests. The only authorized tag, `20260803T010333Z`, was launched once.

Structured result:
`data/laguna-exact-small-postrecovery-smoke-20260803.json`, SHA-256
`201e32b80017a3f8fdc3ab06b786cceb3ae4e57bb5a3fef253020312928ef40a`.

## What happened

Prestart identity, model-manifest, runtime, boot, kernel, taint, BDF/DRM,
process, listener, service-unit, interface, swap, and device-journal checks all
passed. The target and draft loaded successfully. vLLM reported `17.27 GiB`
for model loading, `5.92 GiB` available KV-cache memory, and a 114,030-token
GPU KV cache.

During KV-cache initialization, before graph capture or API health, the 1 Hz
host guard observed:

- `MemAvailable=16,013,720 kB`;
- `SwapFree=341,476 kB`;
- frozen combined boundary: when memory is below `16,777,216 kB`, swap must
  remain at or above `4,194,304 kB`.

The wrapper therefore terminated the runner. The shutdown trace in
`server.log` is the consequence of that bounded stop, not an independent
candidate failure. No request began, no output token was produced, and no
throughput or correctness result exists.

Initialization did prove the exact M12 shared-elementwise and mapped-tail
enable markers on all four ranks. It also logged one profile-time
`num_rows=8192` marker per rank. It did **not** reach the required real-request
`num_rows=12` markers, mapped-tail dispatch markers, post-health worker
environment proof, or grouped-DSO map proof. These partial markers must not be
treated as integration success.

## Teardown and evidence

The runner recorded `stop_status=0`, `worker_status=0`, and `idle_status=0`.
The outer wrapper recorded `cleanup_status=0`, `terminal_audit_status=0`, and
`seal_status=0`. At terminal audit there were no surviving model processes,
protected listeners, DRM openers, or device-journal matches. All four devices
remained bound to `xe`, the boot and kernel were unchanged, ordinary
`/swap.img` recovered to `8,205,016 kB` free, and both artifact roots are
sealed read-only.

Campaign:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T010333Z-campaign`.

Smoke:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T010333Z-smoke`.

## Decision

This is a consumed resource-gate failure, not evidence for or against the
exact-small optimization. Do not retry the tag or execution lock, do not score
or submit it, and do not unlock the endpoint. A future model attempt would
need a new preregistration and lock with an explicit resource change supported
by the successful scheduler-pair resource history; until then, continue with
offline/source/component work only.
