# LocalMaxxing Submissions

Use this page as the canonical pointer for LocalMaxxing submission credentials
and result-submission hygiene.

Submitted-result ledgers and public IDs are tracked in
[../results/localmaxxing-submissions.md](../results/localmaxxing-submissions.md).
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
- primary metric is median tok/s for generated tokens 1-100 after TTFT across
  the suite, with p10, mean, TTFT, wall tok/s, full 512-token tok/s,
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs recorded.

The submission helper fails closed unless payload `engineFlags` include a
realistic-suite gate pass marker and `primaryMetricName` is
`median_tok_s_1_100_after_ttft`.

Do not submit a fresh-response record when the speedup depends on prior
generated continuation history, n-gram history, prefix/cache reuse, context
checkpoints, or response reuse. Label those results as warmed/history
throughput instead.
