# Coding usefulness and lab-memory evaluation — October 7 UTC

Status: CPU preparation and controls only. **No model trial has run on this
packet.** The purpose is to measure completed, reviewable work before combining
the local coding worker with the long-context project.

## What is frozen

- [Task set A](tasks-a/README.md) and [task set B](tasks-b/README.md): real historical
  bugs, pinned to the actual pre-fix commits. Each has a natural issue, independent
  acceptance check, failing-baseline control and passing historical-fix control.
  Review-only patches and fixed-commit receipts stay outside acceptance mounts.
- [Lab-memory packet](memory/README.md): ten source-backed questions with a frozen
  small corpus and a separate answer/citation rubric. This is a decision-recall
  and evidence-use test; it does not measure million-token capacity.
- [Worker profile](worker-profile.json): existing readable observations,
  28,000-token input budget, 2,048-token output cap, 40 steps, 20-minute task
  limit and three acceptance attempts. No inference tuning was performed.

These cases are new to this worker evaluation harness, not provably unseen in
model training. Historical-fix controls prove the checks distinguish those
revisions; they do not prove a model can solve the issue or that every possible
incorrect patch is caught. Review remains required.

## First model trial, when ready

Use `lab-catalog-pending-headlines` and `lab-context-number-boundaries` from set A
first, in that order: one user-facing catalog issue and one research correctness
issue. Run one attempt per task with the frozen profile. No hinting, checkpoint
reuse, source edits, reruns or mid-trial prompt changes. Count timeouts, invalid
patches and exhausted budgets as failures. Halt new requests on runtime faults;
never cycle the server to rescue a failed task.

Record task, model revision, complete server/quantization/KV/run identity,
profile and acceptance hashes, calls/tokens, elapsed time, accepted patch hash,
review outcome and minutes of reviewer intervention. The primary outcome is
independently reviewed correct patches per attempted task. Report test passes
and reviewer acceptance separately. Throughput is secondary. No automatic merge.

If both fail, diagnose their recorded failure category once and prepare one
specific change; do not spend the session tuning prompts against the same cases.
If either passes independent review, run the remaining frozen tasks, once each,
without tuning. Report the initial two and full-set outcomes separately. Later
improvements need fresh tasks to support a generalization claim.

Before using the memory packet, give the answering model only its model-facing
questions and corpus. Keep reference answers and validation receipts out of its
context. Score answers and citations independently with the rubric. Establish
that small source-backed baseline before trying retrieval or durable memory.
Only connect memory to coding after each component demonstrates useful results.

## Runtime admission — currently blocked

At preparation time on the four-card host, the worker virtual environment,
pinned CPU sandbox image, official Qwen3.8-27B-FP8 model and documented R314
runtime inputs were absent. The two-card host belongs to the protected context
experiment and its queued durable pilot. Do not borrow its endpoint or enqueue
another server. LTX and Flash-Next remain parked.

Root storage has about 54 GiB free with a 50 GiB reserve. The worker makes an
archive plus two full source copies; budget all three, the container image,
dependencies, output and concurrent writes before launch. CPU control scripts
use explicitly scoped snapshots, **not** full worker sandboxes. Their success
is not proof that a full snapshot, Docker environment or model runtime is ready.
Do not silently trim the model's source snapshot to make storage fit.

When host ownership, qualified runtime and storage are actually available:

1. Re-read `CURRENT.md` and verify ownership and the intended runtime inputs.
2. Run `scripts/check-storage-headroom.py` with the full peak-write estimate.
3. Install pinned worker dependencies/sandbox only within that admitted budget.
4. Use one bounded, qualified model-server experiment for the trial; stop it
   gracefully afterward. No resident hosting or restart loop.
5. Use the normal worker runner with the matching packet acceptance directory:

```bash
# Template only: OUT must be a new admitted directory outside the repository.
# Use the worker's pinned virtual-environment Python after setup/qualification.
python worker/run.py \
  --repo /home/steve/llm-optimizations \
  --task experiments/local-coding-worker/evaluation-20261007/tasks-a/lab-catalog-pending-headlines.json \
  --acceptance-dir experiments/local-coding-worker/evaluation-20261007/tasks-a/acceptance \
  --config experiments/local-coding-worker/evaluation-20261007/worker-profile.json \
  --out "$OUT"
```

Do not override the task's source commit. Use `tasks-b/acceptance` for set B.
Only issue text and acceptance command enter the model prompt; the source is
pinned before the historical fix. Never mount the packet root, review-only gold
patches, reference answers or live repository into the coding sandbox.

## Next priorities

Run the small coding trial when admitted, then evaluate source-backed lab recall.
Use those results to decide whether connecting the two is worthwhile. The next
model-package milestone is an end-to-end correctness-qualified Qwen TP2 run with
its exact inputs. Resume LTX and Flash-Next from their existing ledgers afterward;
no new weight download or hardware-tuning campaign is justified by this packet.
