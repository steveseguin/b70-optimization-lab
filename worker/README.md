# Local coding worker

Give the worker a repository and an issue. It reads code, edits a source snapshot,
runs tests, and returns a patch for review. The model runs locally on your two
B70s; coding commands run in an isolated CPU container.

This first version uses the qualified **Qwen3.8 27B FP8 / MTP1 / 32K-input**
setup and [mini-SWE-agent 2.4.6](https://github.com/SWE-agent/mini-swe-agent).
The [first milestone](PLAN.md) covered five real bugs across two repositories:
three produced patches that passed independent tests and agent review; two
remain unsolved. This first profile is not dependable unattended coding.
Read the [trial results and patches](../experiments/local-coding-worker/README.md).
Automatic tests, independent agent review, and human approval are reported separately.

## Install

You need the FP8 package's working GPU/Docker setup, Python 3.11 or newer with
venv support, git, and Docker access as a normal user. From this repository:

```bash
worker/setup.sh
```

This creates `~/.venvs/neural-worker`, installs hash-locked dependencies and pulls
the public CPU sandbox image by digest. It does not change GPU drivers or start
or restart a model server. Set `NEURAL_WORKER_VENV` to use a different environment.

## Start the model once

Follow the [FP8 quickstart](../packages/qwen38-27b-fp8-tp2-b70/README.md) to pull
its pinned image and verify/download the model. Then leave one server running:

```bash
python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --model-dir /absolute/path/qwen3.8-27b-fp8 --state-dir /absolute/path/new-worker-server --port 18124
```

Wait for `Ready`. The worker defaults to `http://127.0.0.1:18124` and model
`qwen38-27b-fp8`. Keep other requests off this endpoint while a task is running.

## API and capacity

The running service exposes an OpenAI-compatible Chat Completions API:

| Setting | Current worker service |
| --- | --- |
| Base URL | `http://127.0.0.1:18124/v1` |
| Model name | `qwen38-27b-fp8` |
| Authentication | No key; bound to loopback on this host |
| Requests | `POST /v1/chat/completions`, including streaming |
| Active generations | One; additional requests queue |
| Total context | 33,024 tokens, including input and generated output |
| Worker input budget | 28,000 tokens, including instructions and conversation |
| Speculative decoding | MTP depth 1, two B70s; prompt caching disabled |

The service has not been qualified for multiple simultaneous users. Keep the
endpoint exclusive while the worker records per-request server-prefill metrics.
The model's advertised maximum context is larger than this deployed setting.
Changing a client token limit does not increase the server's capacity.

For a simple non-thinking streaming request:

```bash
curl --no-progress-meter http://127.0.0.1:18124/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-27b-fp8","messages":[{"role":"user","content":"Explain prefill in one sentence."}],"temperature":0,"max_tokens":512,"stream":true,"chat_template_kwargs":{"enable_thinking":false}}'
```

Client profiles select thinking, sampling and output budgets separately from
the loaded server. The [original profile](config.json) uses greedy generation,
thinking disabled, and a 2,048-token output cap. Profile experiments and their
qualification status are recorded in the [worker results](../experiments/local-coding-worker/README.md).

## Give it work

Write the issue in a text file, then run:

```bash
worker/neural-worker --repo /absolute/path/your-repo --issue-file /absolute/path/issue.md --test-command 'python3 -m unittest discover -s tests' --out /absolute/path/new-worker-task
```

The repository must be clean. The worker snapshots its current commit; it never
mounts or edits the original checkout. `--commit` selects an exact earlier commit.
The output directory must be new and outside the source repository.

For a pinned task from the initial queue:

```bash
worker/neural-worker --repo /absolute/path/b70-optimization-lab --task worker/tasks/lab-download-manifest-paths.json --out /absolute/path/new-download-task
```

Run one task at a time. When the model submits, the acceptance command runs. A
failure is returned to the model for correction, up to the configured limit.
Your custom test command must work inside the CPU image: Python standard library,
Node and ordinary shell tools are available; network access and package installs
are disabled during tasks. The bundled checks are mounted read-only.

## Review the result

Each output directory contains:

- `changes.patch` and `changes.json`: patch, changed paths and hashes.
- `result.json`: acceptance status, timing and any failure.
- `baseline-validation.json` and `validation-*.json`: original and candidate tests.
- `trajectory.json` and `requests/`: full local agent conversation and API evidence.
- `baseline/` and `workspace/`: original source and edited snapshot, without `.git`.
- `sandbox.json`: exact CPU container identity and stopped status.

`tests-passed-awaiting-review` means the independent tests passed; read the patch
before applying it. `incomplete` means a test, limit, API request or tool failed.
The worker never merges, commits, pushes, contacts others, or restarts the model.
You can inspect a patch with `git apply --stat /path/changes.patch`; applying it
is a separate user action against the intended source commit.

The default limits are 40 model steps, 20 minutes per task, 28K input tokens,
2,048 output tokens per step, and three completion checks. No automatic context
truncation hides earlier instructions. Three identical consecutive commands trigger corrective feedback; a fourth stops
the task. CPU commands have a 120-second limit and
10 KB returned output. See [config.json](config.json) for the fixed first profile.

## Stop

The task's CPU container is stopped before patch export. Its record is retained.
The FP8 service stays available for the next task. Stop it explicitly when done:

```bash
python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py stop --state-dir /absolute/path/new-worker-server
```

Reading speed uses server-prefill timing; writing speed uses received token
intervals; first-token wait includes the API/transport. Task input sizes change
as the conversation grows, so these results are not a replacement for the
[fixed-input prefill benchmarks](../experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).
