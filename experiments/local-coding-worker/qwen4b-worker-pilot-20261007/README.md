# Qwen3.5 4B worker pilot, October 7 UTC

Preregistered, not yet run. This separate pilot tests whether a small local
model can complete two frozen coding tasks. It is not evidence for the 27B
candidate, a new benchmark record, or an unseen-task quality estimate. The 0.8B pilot never reached either coding task; its minimal-prompt
format gate failed before any task was sent.

The model is `RedHatAI/Qwen3.5-4B-quantized.w4a16`, revision
`7a613872f394578b0b52b683ff4ac47516b4bcaf`, staged at
`/dev/shm/qwen35-4b-worker-20261007`. The copied publisher manifest pins all
three LFS files and nine small files. The supervisor verifies sizes, SHA-256
and Git blob identities before any GPU probe. The MTP weight file is preserved
and verified but speculation is disabled. The model staging is temporary;
this launcher neither downloads nor deletes it.

Use the existing R276 image
`sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`.
One GPU, TP1/PP1, INT4 weights with FP16 activations, automatic FP16 KV,
16,384 context, one sequence, 512 batched tokens, GPU memory utilization 0.5,
eager execution, no prefix caching and no MTP. Prompt-token details remain
enabled for strict accounting. Set `VLLM_XPU_FP16_LINEAR_ROWCHUNK=32`
explicitly: the historical FP16 package used the R224 32-row path, documented
in [the 4B recipe](../../../repro/qwen35-4b-w4a16-b70/README.md#many-users-faster-still-exact-the-class-consistent-fp16-linear-r293-2026-09-11)
and its launcher comments. This is the pinned lab runtime, not stock vLLM.

The corrected container supervisor retains host/device locks, fresh four-card
admission and healthy-only postflight, journal and OOM monitoring, exact
container ownership checks, and one graceful SIGINT with no restart or hard
kill. Root filesystem and model bind are read-only; `/tmp` is capped at 2 GiB;
container memory and combined memory/swap limits are both 24 GiB. The API
binds only `127.0.0.1:18125`. Preserve existing host settings. A device/runtime
fault stops new requests and ends the attempt; an ordinary coding failure
does not cycle the server.

After admission, use the unchanged `worker.run.SYSTEM` and the same instance
wrapper with a neutral print-pilot-ok issue for one transport canary through
the actual worker adapter. Use the frozen profile limits/options and disable
thinking. This differs from the earlier tiny prompt and supports no quality
comparison. Require exact prompt-token
accounting, returned token identities, zero cache use and valid action format.
Do not execute its proposed action. If the gate fails, stop this attempt.
Otherwise reuse the same server for these tasks once each, in this order:

1. `lab-catalog-pending-headlines`
2. `lab-context-number-boundaries`

Each task uses the unchanged frozen `evaluation-20261007/tasks-a` task and
acceptance files, 20 model steps, ten minutes and at most three acceptance
checks. There are no task hints or reruns. The profile allows 12,000 input and
2,048 output tokens, within the 16K server context. Report each result and
failure separately, including format, budget and runtime failures.

Operational paths and prepared entry points:

```bash
python3 experiments/local-coding-worker/qwen4b-worker-pilot-20261007/serve_r276_once.py \
  --out /home/steve/worker-qwen4b-pilot-20261007/server
# After the transport gate passes, with the same server still running:
python3 experiments/local-coding-worker/qwen4b-worker-pilot-20261007/run-task.py lab-catalog-pending-headlines
python3 experiments/local-coding-worker/qwen4b-worker-pilot-20261007/run-task.py lab-context-number-boundaries
```

The task helper uses unique `/dev/shm/worker-qwen4b-20261007-TASK` scratch
and durable `/home/steve/worker-qwen4b-pilot-20261007/TASK` receipts. It refuses
existing attempt directories, checks free scratch/RAM/disk, mirrors compact
evidence while running and retains full scratch afterward. The inherited
campaign `heldout` field denotes tasks withheld from this model trial; their
historical gold fixes are separately preserved and never supplied to the model. Freeze-check, archive and verify the full source inventory, patch and
receipts, including an independent review bound to exact identities, before
removing only owned scratch. The campaign sets `review_identity_required=true`;
keep the source tree clean throughout both tasks. Stop the server with its
`server/STOP` file after both tasks; review cleanup and postflight receipts.
