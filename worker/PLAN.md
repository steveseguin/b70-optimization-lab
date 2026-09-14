# Local coding worker: first milestone

The goal is a local AI worker that takes an issue, investigates the repository,
makes a focused change, runs tests, corrects mistakes, and returns a reviewable
patch. The first milestone is five real issues across the lab and ML Bottleneck
repositories. No runtime optimization campaign is part of this setup.

## Fixed first version

- mini-SWE-agent 2.4.6 with a loopback-only chat adapter. It uses text command
  blocks so the already qualified FP8 runtime needs no tool-parser change.
- Official Qwen3.8 27B FP8, public R304 image, two B70s, fixed MTP1, total
  capacity 33,024, batch 4,096 and one active sequence. Reuse the unchanged
  package `serve.py` launcher and a new state/cache directory.
- One persistent model server. Check CURRENT, actual containers, listeners and
  render owners; run small compute/XCCL preflight under the existing lane lock.
  The helper monitors the journal and owns graceful fault cleanup. Failed
  clients never cycle the model server. Leave a healthy service available for
  subsequent worker tasks and record its exact state path in CURRENT.
- Each coding task gets a committed source snapshot without a Git worktree.
  A separate CPU-only container mounts the editable snapshot and read-only
  acceptance checks. No network, host checkout, credentials, Docker socket or
  GPU is exposed. Root filesystem is read-only; CPU, memory, process count,
  command output and command duration are bounded.
- Pin the public Node/Debian sandbox image by digest; it supplies Python 3,
  Node, git, curl, grep and core shell tools. Python dependencies are hash-locked.

## Five tasks

The task JSONs in `tasks/` record exact source commits, natural issue statements
and independent acceptance commands. The failures were reproduced before the
model saw them; no bugs were injected and no solutions are supplied.

1. Lab: manifest paths with apostrophes break model downloads.
2. Lab: the smoke client sends a second generation after the first request fails.
3. ML Bottleneck: returned hardware listings can mutate the engine's catalog.
4. ML Bottleneck: explicit zero electricity price or operating hours is ignored.
5. ML Bottleneck: malformed numeric CLI options cause internal errors.

Require the original acceptance check to fail and the candidate check to pass.
Allow at most 40 model steps, 20 minutes per task, and three completion/acceptance
attempts. Each call uses greedy sampling, reasoning disabled, 2,048 output tokens,
and an exact tokenization check below 28,000 input tokens. HTTP errors or GPU
faults stop new model requests; no transport retry, cloud fallback or server
restart. A format correction is a new agent step with feedback, not an HTTP retry.

Retain the original failing test, conversation, full request/response streams,
commands, final acceptance checks, changed-file hashes and patch. Report elapsed
issue-to-patch time, input/output counts, HTTP first-token wait, and server-prefill
histogram timing separately. Workloads differ; these are task observations, not
new benchmark headlines. Reject incomplete results and review each passing patch
before calling the issue solved. Never have the model merge or publish changes.

## Completion

Finish with an installed `neural-worker` command, runnable configuration and
instructions, a working FP8 endpoint, task outcomes and reviewable patches.
Publish the worker source and honest setup/result documentation in the lab repo.
The larger product goal remains useful unattended local software work; five
scoped issues alone cannot establish broad agent capability or long-run safety.
