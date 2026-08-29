# Flash-Next post-reboot recovery Stage B3 preregistration

Date: 2026-08-28  
Status: frozen before execution

## Purpose and boundary

The post-reboot Stage A3 gate passed per-card compute, four-rank XCCL, all
twelve directed peer-access queries, storage, memory, source, and bounded B70
journal checks. Its contract authorizes exactly one fresh known-good generation
canary before unrelated model work resumes. Stage B3 is that canary.

This is a recovery diagnostic only. It grants no speed, quality, coverage,
matrix, package, deployment, or LocalMaxxing credit. It cannot replace or
lower any captured result.

## Frozen identity

- measuring host `steve-b70s`, all four B70s, clean synchronized `main`;
- exact successful Stage A3 artifacts at
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-a3`,
  including its self-verifying manifest;
- reviewed supervisor SHA-256
  `2b2a172a94fc23d910e99ea7bbf73200aeb59ee902176e660cb9c1e8fcfe28c4`;
- reviewed one-request client SHA-256
  `5790945842fd3a6c6c7e599df7fbbc6b69b1de40d46d9848ed53939508410f6e`;
- base launcher SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- local-NVMe `Qwen3.8-Flash-Next-FP8`, TP4/EP4, eager, MTP0,
  configured length 512, the already-qualified runtime/source/model identity;
- unique Stage B3 root, attempt 29, state namespace, caches, RPC paths, and port
  19667.

The executable renders the two reviewed recovery scripts mechanically into the
new namespace, hashes both rendered bytes, and retains those hashes with the
source hashes and Stage A3 manifest. It makes no semantic launcher change.

## Exact gate

Launch one bounded fresh server, wait for `/health`, then send exactly one
request: `Reply with exactly: OK`, thinking disabled, greedy, seed 20260609,
maximum eight tokens. Require HTTP 200, normal stop, normalized `OK`, frozen
output hash, exact 17/2/19 usage, and both cache counters zero. Only after the
complete receipt exists may the controller request shutdown.

Require supervisor return zero, descendant-aware cleanup, no remaining server
group, listener, compile path, or RPC path, all four cards rediscovered below
the idle-memory ceiling, and no new B70 reset/fatal journal event. Preserve and
hash every controller, server, request, and postflight artifact. Any failure stops the recovery chain;
it does not authorize a retry, reload, or model arm.

Executable:
`../tools/run-post-reboot-mtp0-512-canary-stage-b3.sh`.

A complete Stage A3 plus Stage B3 pass restores host permission for one newly
preregistered Qwen3.8 AutoRound INT4 correctness diagnostic. That later arm
must carry its own identity, scope, storage, correctness, and stop rules.
