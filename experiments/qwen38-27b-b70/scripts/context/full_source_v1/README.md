# Two-call direct full-source screen

Separate implementation of the frozen
[prospective plan](../../../notes/2026-10-07-full-source-screen-plan.md).
This client makes exactly one request for t01-clinic, then one for t02-theatre.
It does not start a server or admit execution. The supervised host must first
satisfy the plan's prior-campaign, release, health and qualification gates and
hold the model lock for the whole client process. This client does not reacquire
that lock.

Preparation copies hash-pinned source, adjudication, both annotations, the plan
and the feasibility receipt into a new packet. It uses the frozen pure task
compiler by an isolated module name; there is no model import. Requests must be
byte-identical to the feasibility candidates. The CLI cannot substitute a model,
modify questions, omit batches or revise generation settings. No annotation or
reference field is included in the request. Packet creation is CPU-only.

```sh
python3 client.py --prepare --out /path/to/new-packet
python3 client.py --validate-packet --packet /path/to/new-packet
python3 client.py --stub --packet /path/to/new-packet --out /path/to/new-stub-output
python3 -m unittest test_client -v
```

API: `prepare(out)`, `validate_packet(packet)` return `{plan, tasks, requests}`;
`execute(packet, out, endpoint, model, identity, stub=False)` returns the summary.
Packet and results must be separate; output is fresh-only. After separate host
admission, the existing local endpoint interface is:

```sh
python3 client.py --execute --packet /path/to/prepared-packet \
  --out /path/to/new-output --endpoint http://127.0.0.1:PORT/v1 \
  --model qwen38-27b-fp8 --identity /path/to/launch.json
```

One 600-second wall-clock alarm covers each HTTP exchange, with a matching socket
timeout. Redirects, proxy use, HTTP retries and continuation are disabled. A valid
HTTP envelope containing malformed model JSON, incomplete coverage or a non-stop
finish is a bounded failed result and the next fixed trial proceeds. HTTP/transport,
invalid-envelope, source-integrity and persistence failures abort the campaign.
A started partial row is `incomplete`; an untouched row remains `unstarted`.
Returned model identity is checked when present. Response envelopes are bounded
at 2 MiB; excess data is explicitly truncated/infrastructure, never a success.

Each case preserves exact `request.json`, `response.bin`, `transport.json`, launch
identity, `result.json` and `timing.json`. Duplicate JSON keys and nonfinite JSON
numbers are rejected. Scores use exact declared types (bool is not int) and the
same per-category arithmetic as the history task. Null may complete a submission
but is incorrect. Extra fields, unknown IDs, wrong types or missing IDs cannot
complete the protocol. A non-stop response may retain diagnostic answer scores
but cannot pass final-task quality. A stop/valid submission with wrong answers
is completed execution with failed final-task quality.

The protocol is `direct-full-source-screen-v1`; schemas are `full-source-plan.v1`,
`full-source-trial.v1`, `full-source-summary.v1` and `full-source-timing.v1`.
The summary retains both planned rows and terminal result/timing hashes.
`final_task_success` requires a real model, valid stop submission and 24/24;
stubs can never set it. Checkpoint/event quality is always null because this
method produces no intermediate states. Cold interpretation needs known nonnegative integer prompt/completion/cache
counts, zero cached tokens, cached <= prompt, and consistent total/reasoning
counts when reported. Descriptive cost eligibility additionally needs exact final
answers. Missing or inconsistent usage affects cost eligibility only; raw cache
facts and answer quality remain separate. Unknown usage is not zero.
Speed/holdout flags remain false.

`request_seconds` measures the endpoint exchange. `task_seconds` starts before
request persistence and ends after the result is flushed/fsynced, including raw
response persistence. The separate timing receipt binds the result hash; its own
write and offline audits are explicitly outside that boundary. Packet preparation
and supervised server lifecycle costs are separate. This screen does not offer
matched streaming checkpoint guarantees or establish a general speed benefit.

The separate [independent auditor](../audit_full_source_v1.py) reconstructs the
requests and grading without importing this client or opening the local tokenizer:

```sh
python3 ../audit_full_source_v1.py --out /path/to/output --packet /path/to/packet
```

The [supervised owner](../full_source_v1_host_runner.py) reuses frozen qualified
lifecycle helpers. Passive `--prepare` requires all eight prior history outcomes,
their negative continuation decision, same-boot STOP/card/health evidence and a
byte-verified archive whose restored independent audit matches. Its separate
one-shot `--execute` holds the model lock continuously through qualification,
both requests, auditing, STOP and postflight. A safely released client failure
still receives postflight checks and remains failed. Execution belongs in the
documented systemd owner, not an interactive client command or resident service.
