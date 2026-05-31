# LocalMaxxing

Use this folder for queued payloads and responses for DeepSeek V4 Flash
AutoRound.

Existing submission helper:

```bash
cd /home/steve/llm-optimizations
LMX_API_KEY=... scripts/submit_localmaxxing_results.py \
  --payloads experiments/deepseek-v4-flash-autoround-vllm/localmaxxing/queue.json \
  --label <label>
```

The API key should come from the environment. Do not commit secrets.

Submission rule: only submit significant, quality-gated results or a deliberately
useful first baseline. Archive the response next to the payload and add a row to
`../results/experiment-ledger.md`.
