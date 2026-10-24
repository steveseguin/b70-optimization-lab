# Campaign 62: remove recorded reasoning only from the reviewer's evidence packet

Registered after campaign 61 completed October 23 at 21:01 EDT, before any campaign-62 model call.
Campaign 61's neutral reviewer corrected the observed audit denial with thinking on, but its preceding
cuts exhausted the cap and one cancellation condition still denied real receipts. No mode qualified.

## One controlled change

Use campaign 61's exact six frozen campaign-60 candidates, review prompt, source fixtures, ordering,
model/server identity, temperature zero, medium effort, thinking off/on and 8,192-token cap. Twelve
conditions, one call each. The only evidence change is to remove `reasoning_content` and `reasoning`
fields from assistant messages under the packet's `source_turns`. Preserve every original message,
order, archive ID, visible assistant content, tool call/argument, tool result and user instruction.
Opening messages, prior notes and candidate updates stay unchanged. No task-specific guard or answer
is added. Original fixtures retain all removed bytes; projection receipts bind their fields/hashes.

Measured source burden: the observed/cancellation cut has 54,457 characters of assistant reasoning,
290 of visible assistant content, 3,824 of serialized tool calls and 11,365 of tool observations.
The preceding cut has 10,394 reasoning characters and 11,536 tool-observation characters. The local
Qwen template preserves supplied thinking by default; this material is not assumed invisible.

This is a **lossy diagnostic view for a separate reviewer**, not removal from the agent's history,
an exact whole-history transformation, or a qualified default. Reasoning may contain useful deductions;
the experiment must show whether this narrower view helps this failure without losing visible work.
The original records and candidate notes remain available for auditing.

## Prediction and gates

Hypothesis: reviewer thinking on finishes both preceding-cut candidates within the existing cap and
retains the delivered unfinished work; both observed-audit candidates and both cancellation candidates
preserve actual receipt/write history and the authorized pending deletion where applicable. Stronger
screen: thinking off also corrects both false audit denials. Neither is assumed true before the run.

Apply campaign 61's same source-accessible claim audit to all twelve conditions. Do not invent certainty
about earlier ticket identities whose original notices are outside the selected cut. Distinguish
inherited errors from newly asserted claims, actual tool observations from task authority, and queue
exhaustion from the observed state of unfinished repairs. Treat cap, empty and malformed replies as
failed conditions; no fallback/retry and no dropping failed conditions from the matrix.

- One reviewer mode passes all six candidates: require a fresh-server confirmation before a full pi
  transfer trial; do not adopt from this diagnostic.
- Partial benefit: retain exact improvements and remaining defects. Next work must address a specific
  residual mechanism; no generic longer-cap rerun or growing prompt-instruction list.
- No benefit: close reasoning projection for this replay; investigate retrieval of explicit source
  support for uncertain claims, rather than continuing on/off sweeps.

Timings and usage are diagnostic cost only. Source projection changes input; no same-input speed claim.

## Execution and evidence

[Probe](../scripts/context/note_evidence_observable_probe.py) reuses the frozen campaign-61 request,
parser and response checks. CPU checks reconstruct the original request from removed fields and
require that no other field changes; existing malformed/truncated/tool-call rejection remains.
[Runner](../scripts/context/run_campaign62.py) requires stopped prior servers, inactive units, a
hash-bound independent review, CPU checks and fresh output paths. One fresh server and 1,800-second
queue cap, existing fault/memory guards and graceful shutdown, no resident server.

Unit `ctx-campaign62`; raw result `context-longrun-20261016/c62-K32V-check-s0.json`; runner receipts
under `context-longrun-20261016/campaign62-note-observable-review/`. Parent remains active through
the run and audits it after shutdown. No agent/test/build work alongside the server.
