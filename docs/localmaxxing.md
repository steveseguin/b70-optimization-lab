# LocalMaxxing Submissions

Use this page as the canonical pointer for LocalMaxxing submission credentials
and result-submission hygiene.

Submitted-result ledgers and public IDs are tracked in
[../results/localmaxxing-submissions.md](../results/localmaxxing-submissions.md).
The current Gemma 4 26B Q8 B70 record and host details are also linked from the
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
