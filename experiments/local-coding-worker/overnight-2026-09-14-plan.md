# Overnight worker reliability pass

Authorized window: **2026-09-14 04:40:54–12:40:54 UTC** (eight hours maximum).
Stop new task launches at 12:10 UTC to leave publication time. Finish earlier
once the bounded useful work is done. No model-server restart or runtime change.
The existing FP8 service at 127.0.0.1:18124 is healthy and exclusively reused.
Raw evidence: `/mnt/fast-ai/bench-results/local-worker-overnight-20260914`.

## Question and hypotheses

The first trial passed three of five issues. Hardware-listing attempts repeated
read commands without editing; the zero-cost attempt introduced a variable-name
case error and did not repair it. A read-only audit checked all 101 requests
across those three attempts: message prefixes were preserved, tokenization and
usage counts agreed, and every generation finished naturally. Output caps did
not cause these failures.

The first worker used greedy sampling and disabled thinking. The shipped
[model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/blob/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/README.md)
and tokenizer template support explicit thinking effort and preserved reasoning.
The model card gives different sampling settings for thinking and instruct use.
These are potential application-profile improvements, not inference optimizations
or evidence that previously qualified exact-output recipes changed.

## Registered candidates and decision rule

1. **Thinking low:** enable thinking, explicit low effort, preserve reasoning
   history, temperature 1.0, top-p 0.95, top-k 20, presence penalty 0,
   repetition penalty 1.0, min-p 0, seed 42. Allow 4,096 generated tokens per
   step, including reasoning, within the same 33,024 total server capacity;
   retain the 28,000 input-token limit. Keep the system prompt, escaped-JSON
   observations, 40-step/20-minute task limits and three acceptance checks.
   This changes a complete client profile; do not attribute any gain solely to
   reasoning because sampling and the output cap also change.
2. **Readable observations, only if the first candidate fails the targeted gate:**
   retain the original greedy, non-thinking profile and 2,048 output cap; send
   exit status and actual multiline output in the template-supported
   `<tool_response>` wrapper instead of a JSON-escaped string. This isolates the
   observation representation from thinking. Preserve output bytes, truncation
   notices, boundaries and the complete action/result history.

Before task testing, use CPU fixtures for reasoning parsing, correct history
transport, tokenizer/generation template agreement, refusal of truncated or
cached streams, no execution of commands inside reasoning, and API fail-stop.
At most two protocol-only calls may verify actual stream/history compatibility.
No solution code from the failed tasks goes in the system or issue prompts.

Run each candidate once on both failed tasks from the original pinned source,
and on the successful CLI task as a regression control. Require all three to
pass stable independent acceptance and separate patch review. Keep all failures.
If a profile clears this gate, stop profile search. Run the other two original
tasks and two genuinely held-out issues selected by an independent source audit.
The held-out issue statements and baseline failures must be committed before
running them. Do not tune prompts to their solutions.

Confirm both formerly failed tasks once more in new source snapshots, using
seed 43 if sampling is enabled. These are independent task attempts on the
same server, not fresh-server or deterministic-output qualification. If the
second seed fails, keep the profile experimental and report the inconsistency.
Do not silently select only the favorable attempts.

If neither candidate clears the targeted gate, retain defaults and close the
profile screen. Complete useful CPU reliability fixes, evidence/documentation
and a concrete next-step report; do not start an exhaustive sweep.

## Evidence and boundaries

Preserve the first five-issue frozen packet unchanged. New packets record every
attempt, exact client profile, model/runtime identity, full streams, reasoning
and executable answer separately, token counts, server-prefill time, HTTP first
token wait, stream throughput, tests, patch hashes, and independent agent review.
Reasoning tokens are included in generation cost/speed; do not describe those
as user-visible answer tokens. Report time to executable answer separately.
Passing patch tests is not broad model quality or speed promotion.

All code execution stays in the existing CPU sandbox. Original checkouts remain
unmounted and generated patches remain unmerged. Preserve independent four-B70
LTX work. The server helper keeps fault monitoring; any GPU fault halts new
requests, with no restart/retry chain or host-setting changes. No external
messages, cloud model fallback, new models, or competing GPU work.

Publish verified worker changes, a clear result note, API/profile documentation,
and the website summary. Run the relevant worker/integrity/guide checks and
verify CI, deployment and live pages. Leave the healthy FP8 endpoint available.
