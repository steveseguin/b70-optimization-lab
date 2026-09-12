# MiniCPM5-2B native BF16 baseline quality preregistration

Prepared 2026-09-12 before model execution. Fixed suite files:
`realistic-suite-v1.json` (10 prompts, five classes with two each) and
`quality-canaries-v1.json` (six objectively checked diagnostics).

## Pre-execution amendment: final campaign order and quality budget

This amendment is recorded before any model execution and takes precedence
over the earlier ordered-campaign wording below. Prompt bytes and the512-token
timing cap are unchanged. Realistic timing runs **first**, then objective
canaries, then separate2048-cap completion-quality runs for any truncated
realistic rows. Those extension rows never enter timing, must preserve the
original512-token prefix exactly, and are compared in full across processes A/B.
They can qualify completed-answer quality only for the explicitly labeled2048
quality budget. They cannot turn a truncated512-cap answer into a natural
completion or establish that the512-cap configuration answers every task.

Then run the2K/8K needle screens, all six canary/ten realistic/two context
same-process repeats, and six cache/no-cache8-token diagnostics with
teacher-forced logit comparisons. Process B repeats the whole sequence. The
2048-cap completion-quality rows have a fresh-process repeat but not an
additional same-process full repeat (their512 prefix already has that gate).
Qualification is bounded to native BF16 c1, the declared completed-answer
quality budget, and the tested context range. Timing remains independently
reported for the original512-cap rows; incomplete thought text is never scored
as a complete practical answer. `status=complete` means execution finished,
not that the baseline qualified; the analyzer and explicit semantic adjudication
decide qualification after all evidence exists.

## Identity and promise

Pin official model revision, every weight/config/tokenizer hash, chat-template
text and kwargs, rendered prompt IDs, generation config, torch/Transformers
versions/source commits, XPU compiler/runtime/driver, GPU identity, attention
backend, BF16 weights and KV, device count, and relevant environment flags.
Intended lane: one B70, official native BF16 Llama checkpoint, eager attention,
no quantization, no DSpark/speculation, no torch.compile, no cross-request
cache. Native enable_thinking=True; do not silently change reasoning mode to
make short tests or completion rates look better.

This establishes a defined reference implementation and measures its quality;
it does not prove CPU/XPU arithmetic identity, superior quality to Qwen4B,
benchmark SOTA, or universal losslessness. "Lossless optimization" can later
mean exact outputs against this unchanged declared XPU target on the registered
suite, with separately stated coverage limits. No optimization has yet occurred.

## Minimal ordered campaign

1. On process A run six canaries at a 2048-token cap, greedy natural EOS.
   Cap is fixed, not increased selectively after observing a failure. Retain
   full raw tokens/reasoning and parsed final content. All exact JSON/arithmetic
   checks must pass. Literal copy requires exact content after whitespace trim.
   A truncated or unparseable final answer fails; do not substitute a friendlier
   prompt. These short diagnostics never contribute to throughput headline.
2. Run the complete ten-prompt realistic suite once per fresh-prompt attempt
   with max_new_tokens512 and natural EOS. No token forcing/ignore_eos. Review
   every answer against its explicit required findings, truthfulness, relevance,
   and degeneration checks. A reasoning-only truncated result cannot establish
   practical answer quality even if token timing is available. Record it as a
   quality failure/inconclusive usefulness rather than count thought text as a
   finished answer. Preserve truncation and all stop reasons.
3. Repeat all six canaries and ten realistic prompts in process A with fresh
   request-local caches and compare complete generated token IDs byte-exactly.
   Repetition run is determinism evidence, not another independent headline
   sample. The first realistic attempt remains the timing sample.
4. Terminate process A, recreate process B from the same immutable identity,
   and run all six canaries and ten realistic prompts once. Require exact raw
   token-ID equality against process A, including reasoning and EOS decisions.
   Fresh caches, no response reuse; model weights may be resident per process.
5. Supplementary cache/no-cache check: on the same eager backend and BF16
   target, for all six fixed canary prompts, compare first eight greedy next
   tokens from incremental within-request KV cache versus recomputing the full
   prefix each step. Also teacher-force the same prefixes for logit comparison,
   recording max absolute error, relative L2, top1 equality, and top1-top2 margin.
   Exact tokens are required for this bounded cache-parity gate. Logits may
   differ numerically because operation shapes differ: report that honestly;
   do not call non-bitwise logits exact. A token mismatch stops qualification
   pending diagnosis; never change dtype/backend or cherry-pick prefixes to pass.

Canary and realistic quality results must be kept separate from repeat identity:
repeating the same wrong answer is deterministic but incorrect. A small finite
suite passing is a bounded qualification, not a broad capability certification.

## Timing contract

For every generated ID record its completed device-work timestamp and raw ID.
Text chunks or streamer flushes are not token events. The primary rate is
99/(t100-t1), exactly 99 intervals between the first and hundredth generated
tokens. Report thought-inclusive rate explicitly because native thinking is on.
Calculate median of two prompt rates within each class, then median of the
five class medians. Also retain all-prompt median, mean, p10, TTFT, wall
throughput, and natural-full-completion throughput and counts. If any prompt
has fewer than100 tokens, retain its valid short completion and mark the full
primary headline unavailable instead of removing the prompt or forcing length.
512-token truncations are not natural-full-completion measurements.

Cross-request reused prefix tokens are zero by construction for local HF
requests with a newly created cache each time. Within-request incremental KV
cache is ordinary autoregressive inference and is allowed. Record cache type
and creation/reset implementation; don't assert an absent server cached_tokens
field was measured. Device synchronization used for timing may reduce measured
throughput; document it rather than claiming an uninstrumented speed.

## Decision gates

Baseline qualifies only when model identity is verified, all six objective
canaries pass, all realistic answers meet explicit quality criteria, both
repeat gates pass, and bounded cache/no-cache token parity passes. Performance
availability is an independent gate. If native thinking consumes the512-token
budget before an answer, preserve this fixed baseline as failed/inconclusive
for practical usefulness; any follow-up reasoning budget/mode becomes a clearly
separate preregistered campaign, not a silent mutation of v1.

No result comparison with Qwen4B is authorized by a speed-only baseline. That
needs the same quality tasks and comparable reasoning budget, with uncertainty
and model-identity differences stated. No >200 tok/s or lossless-improvement
claim before matched measured evidence.
