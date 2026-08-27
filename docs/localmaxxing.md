# LocalMaxxing Submissions

Use this page as the canonical pointer for LocalMaxxing submission credentials
and result-submission hygiene.

Submitted-result ledgers and public IDs are tracked in
[../results/localmaxxing-submissions.md](../results/localmaxxing-submissions.md).
Its opening table is the current public-by-model index; the remainder is the
append-only submission chronology. Model result packets are authoritative for
verified measured work that has not yet been submitted.
The current Gemma 4 26B Q8 B70 result packet and host details are also linked from the
Gemma result packet at
[../results/gemma4-26b-a4b-q8-b70/](../results/gemma4-26b-a4b-q8-b70/README.md).

## Credential Source

The LocalMaxxing API key is stored outside this repository at:

```text
/home/steve/.config/localmaxxing/api_key
```

The submission helper first checks `LMX_API_KEY`, then falls back to
`~/.config/localmaxxing/api_key`:

```text
scripts/submit_localmaxxing_results.py
```

Do not print, paste, commit, or copy the API key into a repo. Keep payloads,
responses, commands, result summaries, and LocalMaxxing IDs in Git; keep the
secret itself outside Git.

The current speed-result endpoint is
`https://www.localmaxxing.com/api/speed-tests`; `/api/benchmarks` is reserved
for quality-benchmark suites and runs. Before a real write, validate the exact
projected request against the authenticated no-write endpoint:

```bash
scripts/submit_localmaxxing_results.py \
  --payloads path/to/queue.json \
  --label label-to-submit \
  --server-dry-run
```

The helper accepts a real submission as successful only when the endpoint
returns HTTP 201 JSON with nonempty `id` and `status` fields. An HTML response,
redirected application shell, or generic 2xx response fails closed.

## Submit Flow

For normal local submissions, rely on the fallback key file:

```bash
cd /home/steve/llm-optimizations
scripts/submit_localmaxxing_results.py \
  --payloads path/to/queue.json \
  --label label-to-submit
```

Use `LMX_API_KEY` only when a temporary override is needed for a single shell
session. Never write that override into a tracked script, note, payload, or log.

## Git Exclusion

The repo `.gitignore` and the user global Git ignore both exclude the local key
file and common copied-key variants:

```text
/home/steve/llm-optimizations/.gitignore
/home/steve/.config/git/ignore
```

If a future submission tool needs a new local credential filename, add that
filename to both ignore lists before using it.

## Submission Rules

Only submit a result after the benchmark identity and quality gate are clear.
For Qwen work, verify the full graph/launcher identity before deciding a run is
a new record. For MiniMax, Gemma, DeepSeek, or other lanes, keep the same
discipline: record model, quantization, GPU count, mode, command, environment,
throughput, correctness status, payload path, response path, and follow-up note.

### Package publication review

Every new or materially updated public model package must receive an explicit
LocalMaxxing disposition. Submit it only when it passes the fixed realistic
final gate below, improves or usefully fills a matching model/quantization/GPU
category, and has a complete reproducible evidence packet. Validate the exact
payload with `--server-dry-run`, submit it once, then record the public ID,
queue, receipt, and evidence link in
[`../results/localmaxxing-submissions.md`](../results/localmaxxing-submissions.md).

Record a result as **withheld**, rather than silently omitting or force-fitting
it, when it is aggregate-only, a context-curve point, synthetic or warmed,
based on a short fixture instead of the fixed realistic suite, measured
negative, superseded, duplicate, or missing a quality/provenance gate. The
current API's scalar `tokSOut` is single-stream output throughput; never place
multi-user aggregate throughput in that field. A result can be valuable on
neural.download while remaining ineligible for LocalMaxxing.

For Gemma/Qwen-style optimization records, synthetic or repetitive prompts may
guide search but are not submit-worthy real-world throughput. Promotion and
submission require the fixed realistic final gate:

- each prompt in the fixed suite is run exactly once as a cold response;
- every request reports `usage.prompt_tokens_details.cached_tokens=0`;
- prompt/KV cache reuse, context checkpoints, response reuse, n-gram/history
  acceleration, and warmed repeated prompts are disabled;
- target model and quantization are unchanged;
- speculative decoding/MTP is allowed only when accepted tokens are verified by
  the declared target model;
- primary metric is the conventional median rate for the 99 inter-token
  intervals between generated-token timestamps 1 and 100 after TTFT across
  the suite. Every row must therefore contain at least 100 generated-token
  events. An ordinary EOS after event 100 is eligible; there is no rule that
  every row must reach the request's 512-token cap. Record the requested cap,
  per-prompt output-length distribution, p10, mean, TTFT, wall tok/s, full
  natural-completion tok/s (and 512-token tok/s for cap-limited rows),
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs.

Do not suppress EOS or pad/retry a naturally completed response merely to make
all rows the same length. A natural stop before generated event 100 is
ineligible because the primary 99-interval window does not exist for that row;
a natural stop at 100 or later is valid when every other realistic-suite gate
passes.

The submission helper fails closed unless payload `engineFlags` include a
realistic-suite gate pass marker,
`primaryMetricName="median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"`,
`primaryMetricAggregation="median-of-prompt-class-medians"`,
`primaryMetricAccounting="inter-token-intervals"`, 100 generated-token events,
and 99 intervals. The historical `median_tok_s_1_100_after_ttft` field remains
in old receipts for compatibility but is not eligible for a new submission.

The public API expects `engineFlags` as a typed object and requires a
`commandSnippet` when the object is supplied. The local queue files may retain
richer typed audit metadata for preflight; `scripts/submit_localmaxxing_results.py`
sanitizes that object into the documented API shape at POST time while keeping
the local preflight policy checks intact.

The public API also validates enum and scalar field types strictly. Use
`engineName="llama.cpp"` for llama.cpp/SYCL rapid snapshots, and keep
top-level `promptTokens` / `outputTokens` as integers. Per-prompt token-count
arrays can stay in `engineFlags` for audit detail. The rapid-suite payload
builder rounds suite medians to integer top-level token counts for this reason.

The typed API enum currently has no BF16 KV-cache value and accepts only a
generic `flash_attn` label for FlashAttention. Keep the literal runtime values
in local `engineFlags.kvCacheDtype` and `engineFlags.attentionBackend`, set
`apiKvCacheDtype="auto"` and `apiAttentionBackend="flash_attn"` for that
case, and let the submission helper preserve the literal values in
`extraFlags`. For fully offloaded engines, set `engineFlags.gpuLayers=-1`
instead of relying on the llama.cpp-oriented fallback.

`--allow-non-headline` is for local `--dry-run` inspection only. It must not be
used to post diagnostic synthetic, repeated, warmed, history, or n-gram
artifacts to LocalMaxxing.

Do not submit a fresh-response record when the speedup depends on prior
generated continuation history, n-gram history, prefix/cache reuse, context
checkpoints, or response reuse. Label those results as warmed/history
throughput instead.
