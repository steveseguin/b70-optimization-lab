# Durable context revision 3: bounded reasoning during final answering

The [r2 development run](2026-10-07-durable-context-r2-result.md) retained every
source batch and kept every structured table correct, but final answers confused
past and current values and misassigned evidence to question IDs. The owner
explicitly asked to continue. Preserve r2 and its failed quality gate unchanged.

The next lever changes only final-answer generation: enable thinking with
`reasoning_effort=medium` and `max_tokens=8192`. This is a combined reasoning and
answer output cap per action, not an independently enforced thinking-token cap.
All ingestion and extraction calls remain thinking-off with 4096 output tokens.
The same policy applies to all three methods. Temperature remains zero.

The local model template supports medium effort through `chat_template_kwargs`;
medium introduces no extra effort sentence. The local R314 server counts both
reasoning and answer tokens in completion usage. Preserve its original response
message (including either reasoning field), finish reason and token details in
the call log. Do not infer a zero reasoning-token count if details are absent.
A length cutoff is a recorded failure, with no continuation or retry.

The separate `durable_v3` sources also distinguish malformed model JSON from a
malformed HTTP envelope. Only model-format feedback is recoverable inside the
fixed action budget; transport/envelope failure ends the attempt. This narrows
failure handling without changing successful r2 ingestion or retrieval behavior.

Keep the task generator, exact batch lookup, numeric search boundaries, prompt
layout, saved-answer rules and retrieval permissions unchanged. The working
prompt limit remains 32,768 UTF-8 bytes. Each trial allows at most 32 answer
calls and 24 distinct retrieval operations. Full completion requires explicit
submission covering all 24 question IDs. No oracle enters real model prompts.

Freeze the same six development trials: seed 7, report and dispatch styles,
48 batches, 320 filler words, three methods. Before them, one qualified server
must pass device health, 12/12 standing reference checks and both fixed extraction
diagnostics. All six full development trials must be correct, complete and
unresumed before using held-out seeds 401, 502 and 603 in both styles (18 trials).
These held-out tasks remain unused as of this preregistration.

One fresh supervised server serves this revision, with no automatic retry,
resident service, reset or power/memory-setting change. Stop it on completion
or failure. Preserve every outcome. A failed development gate keeps the holdout
unused. Record observed reasoning cost as part of total cost; no speed claim
qualifies without the unchanged full quality and paired timing gates.

Implementation: `scripts/context/durable_v3/` and `durable_v3_host_runner.py`.
Frozen data: `data/2026-10-07-durable-context-r3/`.
Planned output: `/mnt/fast-ai/bench-results/context-durable-r3-20261007`.
Owned unit: `ctx-durable-r3.service`.

If this lever fails, classify the remaining errors before choosing the next
separate development revision. Evidence-linked answers and exact historical
state lookup are candidates, not changes admitted into this frozen run.
