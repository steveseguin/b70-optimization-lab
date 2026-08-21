# Qwen3.8 GPU3 incumbent-control health diagnostic preregistration

Date: 2026-08-21

Status: **implemented, CPU-tested, hash-frozen; not launched**.

This is the only bounded next action permitted by the stopped
[Q64xK32 r2 operator campaign](2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-result.md).
It is a fresh-root infrastructure diagnostic, not another arm of that campaign.
It does not load the Q64xK32 candidate, test candidate correctness or timing,
authorize an endpoint/full-25 run, recover a device, or reuse GPU2 evidence.

## Question and exact scope

Can physical GPU 3 execute ten returned stock FlashAttention calls at the
production-derived KV-128 MTP5/M6 shape and return from the first explicit
`torch.xpu.synchronize()` within a 60-second supervisor deadline?

The worker is fixed to:

- physical GPU `3` selected only by `ZE_AFFINITY_MASK=3`, with exactly one
  visible logical `xpu:0`;
- exact device name `Intel(R) Arc(TM) Pro B70 Graphics` and Torch XPU UUID
  `868023e2-0000-0000-4700-000000000000`; the historically established PCI
  context is `0000:47:00.0`, but the runtime gate uses the UUID rather than
  inferring an ordinal-to-BDF mapping;
- stock stage
  `/home/steve/staged-xpu-commitfix-graphfa-composite-20260820` and its exact
  graph/file identities. The complete 20-file `vllm_xpu_kernels` inventory is
  rederived from
  `repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256`
  at SHA-256
  `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`;
- `VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY=0` and
  `VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY=0` so neither experimental policy is
  selected;
- `VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1`, FP16, rows `6`, local Q heads `12`,
  local KV heads `2`, head dimension `256`, block size `64`, paged causal KV,
  `is_mix_batch=True`, and KV length `128`;
- no XPU graph capture, mutations, timing samples, model load, vLLM service,
  candidate manifest, `xpu-smi`, or device-reset operation.

The selected stage must map only its exact
`_vllm_fa2_C.abi3.so`, `libattn_kernels_xe_2.so`, and `libattn_stock.so` for
those basenames. The worker records the matching `/proc/self/maps` lines and a
SHA-256 of the complete maps view. The Python interface remains an exact
file/path/hash and imported-module-path gate.

## Frozen-code instrumentation

The worker imports the frozen base exact-shape qualifier
`scripts/qwen38_mtp5_m6_fa_operator.py` in memory at SHA-256
`0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f`.
It invokes that qualifier's own `_run_case` at KV 128, but wraps only two
Python call boundaries:

1. each return from `flash_attn_varlen_func` publishes an immutable receipt;
2. the first call to `torch.xpu.synchronize` publishes `sync-enter`, calls the
   original function, publishes `sync-return` if it returns, and raises an
   internal expected-stop sentinel.

The base qualifier's warmup prefix makes exactly ten FA calls before that
first explicit synchronize. The diagnostic therefore stops before the base
correctness, mutation, graph-capture, or timing loops. Ten return receipts do
not prove device completion; `sync-return` is the required completion boundary.

The frozen diagnostic bytes are:

- worker `scripts/qwen38_gpu3_incumbent_control_health_worker.py`:
  `bd8225e30e1335a3fe33e78421b1feb3cfb036ca04d0ca6738cb1eea8639b11f`;
- external supervisor
  `scripts/qwen38_gpu3_incumbent_control_health_supervisor.py`:
  `eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375`;
- CPU tests `scripts/test_qwen38_gpu3_incumbent_control_health.py`:
  `73ff3a5cd881a3a278db96b4b2130f18ddf55b8722bb56182363b36e9c83efc6`.

The supervisor hard-binds the worker SHA. The immutable launch contract binds
the actual supervisor, worker, and base-qualifier paths and hashes; clean
`main == origin/main`; repository HEAD; complete stock-stage identity; exact
environment; device UUID/name/affinity; workload; and deadline. The worker
revalidates those bytes and the stage before importing Torch.

## External watchdog and evidence contract

The supervisor never imports Torch. It creates a new mode-`0700` result root,
an immutable `contract.json`, and a separate append-only supervisor receipt
chain before launching the worker in a fresh session. Every receipt is written
through an exclusive temporary, flushed, `fsync`ed, changed to mode `0444`,
renamed atomically, and directory-`fsync`ed. Each receipt binds the contract
SHA, writer process boot ID/PID/PGID/SID/start ticks, and previous receipt SHA.
The worker must be the leader of
its fresh session (`PID == PGID == SID`), and the watchdog treats every
matching descendant as live even if the leader has already exited.

The worker chain must be exactly:

1. `worker-start`;
2. `base-and-stage-verified`;
3. `device-bound`;
4. `stock-maps-bound`;
5. ten ordered `fa-launch-returned` receipts with indexes 1 through 10;
6. `sync-enter`;
7. `sync-return`;
8. `worker-complete`.

Only then may an immutable `worker-result.json` be accepted. The supervisor
revalidates the chain, every phase payload, result or failure packet, child
boot ID/PID/PGID/SID/start ticks, maps, complete stage graph,
device, workload, and finalized stdout/stderr hashes before writing a passing
terminal packet.

The wall deadline is exactly 60 seconds from immediately before process
creation. On expiry the external supervisor first makes a durable atomic/fsync
attempt for `timeout-before-term`, then sends `SIGTERM` to the worker's process
group when the pre-signal scan proves that group nonempty. If the receipt write
fails, cleanup records the exact failure in its cleanup state and still
terminates the group so the failed evidence write cannot orphan the worker. It
waits five seconds, makes the same durable attempt for
`term-grace-expired-before-kill` if the child remains, sends `SIGKILL`, and
waits another bounded five seconds, makes one final verified best-effort group
kill if members remain, and records the final verification result. Cleanup is
a single non-reentrant state machine: transient group scans, receipt writes,
`killpg` calls (including `ESRCH`), and process disappearance become explicit
errors or disappearance evidence rather than escaping into a second cleanup
or changing a timeout into a supervisor exception. A
`term-grace-expired-before-kill` receipt exists only when a verified nonempty
group remains. Every cleanup also attempts a separate immutable
`cleanup-state.json` packet that binds the child, contract, signals, errors,
receipts, leader return code, and final process-group snapshot.

The primary `child-launched` receipt and its
`child-launched-after-supervisor-error` fallback are nonthrowing durable
attempts. Failure of either is recorded in cleanup state; failure of the
primary immediately enters cleanup, and failure of both cannot bypass group
termination. The same durable-attempt-before-signal sequence applies after a
post-launch supervisor `BaseException` or external `SIGINT` or `SIGTERM`; an
external interrupt is converted to a terminal failure rather than letting the
parent abandon the fresh-session worker. A still-present
matching process-group member is recorded in a bounded immutable snapshot with
`unkillable=true`; the validator checks the recorded boundary without
pretending concurrently writable `.tmp` logs still have the same current
bytes. Immutable receipt bytes remain exact. The output root and its existing
parent must be absolute, canonical, and symlink-free before creation.

Child identity is read twice through the canonical worker helper. If both reads
fail while the known `Popen` child remains available, the supervisor performs
an independent exact `/proc` read solely to bind and terminate the fresh
`PID == PGID == SID` session. It records both canonical-read errors, emits a
distinct `child-identity-unavailable` durable attempt, sets
`child_identity_verified=false`, enters cleanup immediately, and can produce
only the terminal `child-identity-unavailable-{terminated,unkillable}` failure
classification. This fallback identity is never represented as an ordinary
verified launch and can never pass the diagnostic. Its entire group scan and
leader recheck path stays on the supervisor-local `/proc` reader; it does not
silently call the failed canonical helper again.

If both canonical reads and the supervisor-local identity read fail, or if the
supervisor-local cleanup later loses group verification, no child identity is
fabricated. Using only the `Popen(start_new_session=True)` guarantee and
`proc.pid` as the expected PGID, a final nonthrowing emergency path probes
group existence with `killpg(pgid, 0)`, attempts group `SIGTERM`,
waits five seconds, attempts group `SIGKILL` if necessary, waits another five
seconds, and re-probes. It makes best-effort immutable emergency receipt
attempts and writes `unidentified-child-emergency.json` with the acquisition
errors, signal attempts, final group-existence result, and stdout/stderr byte
observations. This path restores the supervisor signal handlers, exits with an
error, never writes the ordinary `terminal.json`, and never authorizes a pass.

The controlled signal handlers remain installed through log finalization,
worker-packet validation, and terminal publication. Immediately before the
terminal transaction, SIGINT/SIGTERM are blocked, pending signals are checked,
and any first unhandled signal enters cleanup exactly once. Signals observed
after cleanup has begun are recorded as late evidence and never re-enter or
reclassify that cleanup. The original handlers and mask are restored only
after the immutable terminal packet is published. If a final-fence signal
starts cleanup, the supervisor reblocks afterward and drains every signal that
arrived during cleanup into late evidence without reentry. That final
post-cleanup blocked pending-signal snapshot is the transaction's
linearization point:
`SIGINT`/`SIGTERM` arriving after that snapshot linearize after immutable
terminal publication and do not retroactively change its classification.

## Decision and terminal rules

A pass requires all exact identity, stage, maps, receipt-chain, ten-return,
and `sync-return` gates before the wall deadline. A pass says only that this
stock KV-128 launch/synchronize prefix completed once on GPU3. It may authorize
writing a separate preregistration for a completely fresh two-GPU eight-arm
operator campaign. It does not itself authorize that campaign or predict its
result.

Any timeout, worker exception, identity mismatch, missing/extra/out-of-order
receipt, maps mismatch, wrong UUID, early synchronize, nonzero worker exit,
invalid success packet, or unkillable process fails this diagnostic. Preserve
that fresh root and do not retry it in place. The Q64xK32 r2 root remains
terminal in every outcome, its GPU2 packets cannot be carried forward, and no
candidate/model/full-25 action is authorized by a failure. Privileged recovery
would require separate explicit authorization.

## Command after commit/push and hash freeze only

The suggested fresh root is
`/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r1`. It must not
exist before launch.

```bash
/usr/bin/printf '%s\n' \
  'eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375  /home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/qwen38_gpu3_incumbent_control_health_supervisor.py' | \
  /usr/bin/sha256sum --check --strict && \
/usr/bin/python3 -B \
  /home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/qwen38_gpu3_incumbent_control_health_supervisor.py \
  run /home/steve/qwen38-gpu3-incumbent-control-health-20260821-r1
```

Do not run while the repository is dirty or local `main` differs from
`origin/main`. Recompute and compare all frozen hashes immediately before the
single launch.
