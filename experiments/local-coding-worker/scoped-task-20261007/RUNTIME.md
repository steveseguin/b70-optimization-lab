# One scoped coding attempt

This is one authorized diagnostic on `lab-worker-action-ready-latency`, a previously unattempted task at `7324c356f00901b4d53f9ec26bda46900294ebb4`. Its original issue and independent acceptance check remain unchanged. The coordinator-selected projection contains 12 pinned files (202,639 bytes), including ancestor AGENTS.md, and permits one new test path. It is a different evidence class from the earlier full-repository trials. The known fix and review-only controls never enter the model context or acceptance mount.

The copied supervisor changes only the served alias, container prefix and fresh restore-summary path. It preserves R276 image `sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`, official FP8 revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, target-only TP2 on cards 0/1, FP16/full FP16 KV, 2 GiB KV per rank, eager mode, disabled prefix caching and the complete prior environment. This does not qualify the newer speculative package. `runtime-plan.json` binds exact files, runtime settings and prerequisites.

The task profile caps output at **512 tokens**, uses at most **12 model steps**, a **600-second agent budget**, and **two acceptance checks** within that same attempt. Thinking is off; temperature 0/top_p 1/seed 42. The existing stream deadline remains 120 seconds. At the prior 9.6065 tokens/sec observation, 512 generated tokens cost roughly 53 seconds before prefill/transport allowance; that is a budget rationale, not a speed promise. The agent budget is checked between turns; the coordinator separately sends one SIGINT to the owned CPU worker at 900 seconds. No output repair, whole-task retry, budget increase or new hints follow failure.

## Reused files and exact invocations

The normal restore entrypoint is `/home/steve/worker-scoped-task-20261007/model-restore/restore.py`, invoked once as `python3 -B <that-path>` with no arguments. Its bytes are unchanged from `../cited-recall-v2-20261007/model-restore/restore.py`; the archived copy is `model-restore/restore.py` here. OUT follows the new script directory. The cold source stays at `/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`; the temporary destination remains `/dev/shm/qwen38-27b-fp8-worker-20261007` and must be absent initially. Restore requires the exact UUID/partition, read-only `norecover` mount, 90 GiB host availability, model bytes plus 24 GiB tmpfs reserve, and a 50 GiB root reserve. It checks all 80 files on source and destination and cleanly unmounts before any GPU probe. Do not invoke the historical script in its old output directory.

The supervisor entrypoint is `serve_r276_once.py --out /home/steve/worker-scoped-task-20261007/server`, using `/usr/bin/python3 -B`. Root must launch it as the systemd-owned `lab-worker-scoped-20261007.service`, with `Restart=no`, `KillMode=process`, `KillSignal=SIGINT`, `SendSIGKILL=no`, and `TimeoutStopSec=infinity`. Its own unchanged 1,200-second lifetime triggers graceful stopping; cleanup can wait longer while retaining locks. Do not wrap it in a restart loop or hard-kill timeout. The runtime alias is `qwen38-27b-fp8-scoped-worker` at `http://127.0.0.1:18125`.

After the normal CPU controls, clean-source admission, restore and same-server boundary/canary gates pass, the worker invocation is:

```bash
/home/steve/.venvs/neural-worker/bin/python -B experiments/local-coding-worker/scoped-task-20261007/run_guarded_worker.py \
  --repo /home/steve/llm-optimizations \
  --task experiments/local-coding-worker/scoped-task-20261007/task.json \
  --config experiments/local-coding-worker/scoped-task-20261007/worker-profile.json \
  --acceptance-dir /home/steve/worker-scoped-task-20261007/acceptance \
  --out /home/steve/worker-scoped-task-20261007/attempt
```

Run from the repository root only through the coordinator that owns lifecycle checks. The external acceptance directory contains only the exact original `worker_action_latency.py` (SHA-256 `db1bc0d85b59979675e388d1f34aebae96cc6ad8b81f0fc0f5c847a0b2e81f9c`). The small source snapshot lives on the internal filesystem and must pass normal storage admission; there is no clean-repository bypass. The code being edited is the historical pinned collector snapshot, while the host harness is the newly frozen reviewed worker implementation.

## Admission, stop and evidence

Keep the existing eight finite 511/512/513/1025 marker/repeat checks and one representative no-execution worker-format canary on this same server. Use current SYSTEM, the new profile and the scoped-notice form; bind the rendered prompt bytes before the canary. The old canary script is a template, not directly runnable with its hard-coded 4B profile. Require exact input accounting, complete token IDs, explicit zero cached tokens, natural stop and one valid command. These controls do not establish general model equivalence. Keep every worker prompt above 300 tokens, avoiding the known one-token runtime path without claiming it fixed.

Before starting the single task require at least 960 seconds remaining from conservative supervisor PID age and at least 24 GiB host MemAvailable. The client coordinator checks live ownership and STOP/FAULT/shutdown before every new generation; any transport/runtime fault halts new requests. It preserves partial streams on interruption and always writes server/STOP in finally. Root owns this controller and its final frozen hashes. No extra permission pause is required once the authorized trial's stated controls pass.

After submission or failure, stop the CPU sandbox before exporting and independently reviewing the patch. Test success alone is not acceptance for merge. Preserve immutable scope identities, source/control receipts, trajectory, raw SSE, response timing, patch, final workspace hash and independent review. Fsync the durable export before removing only owned source snapshots. Wait for the supervisor's single SIGINT, exited container, idle nodes and all-four-card postflight; then rehash the full temporary model against the retained cold-copy identities before releasing RAM. A failed cleanup retains evidence and ownership; no hard kill, server restart, driver reset or two-host operation is introduced. LTX, Flash-Next and the RAM exclusion stay unchanged.

The Qwen DO-NOT-REPEAT index and previous failed worker closeouts were reviewed. This tests a fresh issue under a visibly changed scoped protocol, not a retry of a closed question or an optimization sweep. Report success or failure for this attempt only, without attributing a causal improvement to scope, prompt, token budget or model speed.

The prepared trial-only entrypoint is `run_guarded_worker.py`; it delegates the same CLI to the shared worker while checking STOP/fault/live supervisor boot/PID/start ticks before queries, network opens and CPU commands. It checks natural stop, zero cache and complete token accounting after generation. `check_boundaries.py` and `check_transport.py` use the same guards; the canary exercises the scoped instance-template form with a dummy scope and carries no real-task hint. Three synthetic CPU guard controls passed. Root supplies the outer systemd/client controller and final code bindings.
