# LocalMaxxing

Queued payloads and submission responses for the REAP MiniMax lane.

## 2026-05-31

### Sampled/Default-Temperature REAP Baseline

- Payload: `reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.payload.json`
- Queue: `reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.queue.json`
- Status: submitted and approved.
- LocalMaxxing ID: `cmpub8nkx00pzmq01wjujveuj`
- Submit log: `reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.submit.log`
- Submit command:

```bash
LMX_API_KEY=... \
/home/steve/.venvs/vllm-xpu/bin/python \
  /home/steve/llm-optimizations/scripts/submit_localmaxxing_results.py \
  --payloads /home/steve/llm-optimizations/experiments/minimax-m27-reap-autoround-vllm/localmaxxing/reap-minimax-m27-autoround-ccloverride-p512n1536-20260531.queue.json \
  --label reap-minimax-m27-autoround-ccloverride-p512n1536-20260531
```

The first submission attempt on 2026-05-31 failed before posting because
`LMX_API_KEY` was not present in the environment. The user then provided a key,
which is stored outside the repo at `~/.config/localmaxxing/api_key` with
user-only permissions. `scripts/submit_localmaxxing_results.py` now falls back
to that path if `LMX_API_KEY` is not set.

Correction: this first payload described the run as temperature `0`, but
`vllm bench throughput` defaults to `temperature=1.0` unless
`VLLM_BENCH_TEMPERATURE=0` is set. Treat `cmpub8nkx00pzmq01wjujveuj` as the
default-temperature throughput datapoint.

### Corrected Greedy REAP Baseline

- Payload: `reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.payload.json`
- Queue: `reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.queue.json`
- Status: submitted and approved.
- LocalMaxxing ID: `cmpuc7tkq00qamq01z61pnb3c`
- Submit log: `reap-minimax-m27-autoround-greedy-ccloverride-p512n1536-20260531.submit.log`
- Command includes `VLLM_BENCH_TEMPERATURE=0`.
- Result: `89.18670709734161` output tok/s, `118.91560946312214` total tok/s.

### Greedy REAP pidfd CCL Update

- Payload: `reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.payload.json`
- Queue: `reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.queue.json`
- Status: submitted and approved.
- LocalMaxxing ID: `cmpuesbma00r5mq01yk0zdcjx`
- Submit log: `reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.submit.log`
- Command includes `VLLM_BENCH_TEMPERATURE=0`, `CCL_IPC=pidfd`,
  `CCL_ZE_IPC_EXCHANGE=pidfd`, and
  `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`.
- Result: `89.49922316987691` output tok/s, `119.3322975598359` total tok/s.
- Quality: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T231727Z.json`,
  `passed=true`.
