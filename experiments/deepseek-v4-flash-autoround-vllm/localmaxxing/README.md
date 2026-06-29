# LocalMaxxing

Use this folder for queued payloads and responses for DeepSeek V4 Flash
AutoRound.

Credential location and helper usage are centralized in
[docs/localmaxxing.md](../../../docs/localmaxxing.md). Keep the API key outside Git.

Existing submission helper:

```bash
cd /home/steve/llm-optimizations
scripts/submit_localmaxxing_results.py \
  --payloads experiments/deepseek-v4-flash-autoround-vllm/localmaxxing/queue.json \
  --label <label>
```

The helper reads `LMX_API_KEY` first, then falls back to
`~/.config/localmaxxing/api_key`. Do not commit secrets.

Submission rule: only submit significant, quality-gated results or a deliberately
useful first baseline. Archive the response next to the payload and add a row to
`../results/experiment-ledger.md`.
