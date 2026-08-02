# Laguna 32K context and prompt-processing preregistration

Date: 2026-08-02 America/Toronto

## Protected result and scope

The protected Laguna result remains `125.4619731637751 tok/s` under the
conventional 99-interval metric. It is a short-context BF16-KV, TP4/EP4,
M12/DFlash11 result whose largest prompt has 863 tokens and whose service
limit is 8192. Nothing in this lane changes or relabels that record.

This new lane answers two different questions:

1. how prompt processing scales through a real 32K service identity; and
2. how sustained speculative decode changes as the live KV context grows.

The first baseline changes only service capacity: `max_model_len=32768`,
explicit chunked prefill, and `max_num_batched_tokens=8192`. It keeps BF16 KV,
GPU memory utilization 0.90, prefix caching off, one sequence, synchronous
candidate scheduling, and every promoted M12/DFlash11 selector. No source or
native binary changes are allowed in the baseline.

## Frozen suite and metrics

The suite is `long-context-suite-v1.json`. It has early, middle, and late
fact placement at exact prompt lengths 1024, 4096, 8192, 16384, 24576, and
32640 tokens. Each prompt reserves exactly 128 generated tokens so the largest
request is exactly 32768 tokens. A unique 256-token sentinel follows each
32640-token row to detect cross-request contamination.

Prompt arrays are built locally with the pinned target tokenizer and chat
template, sent as token IDs to `/v1/completions`, and never truncated or
retokenized. Every row must prove:

- returned prompt IDs and `usage.prompt_tokens` equal the exact input array;
- `cached_tokens=0`;
- exact authoritative JSON fields appear at the start of the response;
- 128 output IDs and `finish_reason=length` for long rows;
- one-request Prometheus deltas for prefill time and computed KV tokens; and
- the post-32K sentinel succeeds.

Primary prompt-processing throughput is the per-request Prometheus delta
`request_prefill_kv_computed_tokens / request_prefill_time_seconds`. Client
TTFT and server scheduled-to-first-token time are cross-checks, not renamed as
pure prefill time.

Decode is reported per context row as:

- conventional first-100 rate: `99 / (offset[99] - offset[0])`;
- historical compatibility: `100 / (offset[99] - offset[0])`;
- full 128-token interval rate; and
- server `mean_itl_ms` and generation-time cross-checks.

Accepted and drafted token counter deltas are recorded per row. The target has
12 full-attention and 36 sliding-window-512 layers; the six-layer draft is all
sliding-window-512. Falling draft acceptance for remote early/middle facts is
therefore a measured model behavior, not automatically a kernel regression.

## Correctness hierarchy

Retrieval is necessary but not sufficient. A later candidate promotion must
also match a newly frozen target-only q=1 oracle on every output token and text
hash for these exact prompts. The extended canonical teacher keeps the
established target-only eager, asynchronous-scheduling identity; candidate
DFlash remains no-async. The old short-prompt oracle cannot certify this new
suite.

The first candidate run is explicitly `baseline-oracle-not-yet-tested`. It may
describe capacity, prefill, decode, acceptance, and retrieval, but cannot be
called long-context exact until the new q1 oracle comparison passes.

## Source optimization after baseline

The source audit found the main short-prompt discontinuity. With exact target
arithmetic enabled, target linear and MoE code serializes every row for
`13 <= M <= 512`; the 863-token record row bypasses this fallback and is much
faster. The first source treatment, if baseline evidence still supports it,
will be a default-off pure-prefill selector that groups those scalar rows in
chunks of 8 plus an exact tail. Eight is the proven maximum for the
deterministic direct expert path; M12 is not valid for this purpose.

Eligibility must be set from scheduler/model-runner prefill state, not inferred
from row count alone: one request, prompt tokens still uncomputed, no scheduled
speculative tokens, no graph replay, and no LoRA/encoder/ubatching/cascade.
Decode/verifier M<=12 and the 146/145 target plus 14/13 draft graphs remain
structurally unchanged.

Before an endpoint performance run, the treatment must pass raw BF16 equality
against scalar prompt execution for linear and MoE outputs, final prompt
logits, lengths 511/512, tails 1..7, two sequential requests, and the existing
863-token path. A promoted service candidate must then pass the new 32K oracle
and the complete frozen 13-prompt short record gate without decode regression.

## Stopping rules

Stop and preserve evidence on service startup failure, prompt truncation,
nonzero cached tokens, retrieval/sentinel failure, metric-count ambiguity,
target/draft topology drift, oracle mismatch, surviving workers, or any XPU
runtime/driver health error. Do not reset or reboot hardware merely to rescue
an experiment. `max_num_batched_tokens=16384` and 32768 are separate future
config identities and may be tested only after the 8192 baseline completes
cleanly.
