# Streaming host probe preparation

The additive [host_probe.py](host_probe.py) implements the explicit fixture scope
in [HOST-ONLY-PLAN.md](HOST-ONLY-PLAN.md). It has not started a native owner or
made an HTTP request during preparation. Production service admission remains
unchanged; `FixtureFacade` is visibly synthetic and is never `StreamingChatService`.

Use qualified module invocation. Running this file directly would place the
directory containing `http.py` on Python's import path and shadow stdlib `http`;
the helper therefore refuses direct-script execution before imports.

From the repository root, the read-only plan command is:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=/home/steve/llm-optimizations/experiments/own-xpu-runtime/integration /home/steve/.venvs/vllm-xpu/bin/python -B -m streaming_v1.host_probe --plan
```

After independent source review and explicit root execution authorization,
replace only `--plan` with `--run-host-only` for the single proposed run. The
fixed fresh ignored output is packet198's
`build/engine-integration-streaming-a`; there is no CLI path override or retry.
The same placement/environment prefix followed by
`-m unittest streaming_v1.test_host_probe -v` runs the CPU mocks.

The actual owner is the already compiled GNU HOST_ONLY ELF, pinned by the parent
compile/proof receipts. Native environment and tool environment come from the
existing admitted helper. The decoder's real codec is verified before owner
creation. Four-GiB AS limiting occurs only in the standalone executing probe;
`--plan` and unit tests do not alter memory limits.

One serial listener handles two bounded SSE turns: SAVE then RELEASE, then QUIT
before the native eight-request limit. Callbacks record front state before
terminal consumption, decode exact tiny IDs through the real token byte mapping,
and use the production nonblocking SSE delivery path. Client receive times are
reported without forcing or claiming peer receipt before disposition. Full SSE
captures are bounded to64KiB; failed partial captures preserve bytes, frame data
and original errors. No finish/DONE after a failed stream is accepted.

Predictable plan/codec refusals precede owner creation. On a later incident,
intake stops and cleanup permits at most one cooperative SIGTERM. Any uncertain
Popen/thread start, unreadable owner status, or live owner/handler retains all
borrowed resources. The CLI stays alive for coordinator inspection in that
exceptional state; it does not force-close FDs, kill, retry or launch replacements.
Normal cleanup closes the store only after handler and owner exit.

Preparation evidence is under `receipts/host-preparation.json` and
`receipts/host-plan.json`, with the focused test log. These are CPU preparation
receipts, not a native/model/device qualification.
