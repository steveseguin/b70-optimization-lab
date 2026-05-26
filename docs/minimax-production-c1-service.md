# MiniMax Production C1 Service

This is the recommended production-friendly shape for the current 4x B70
MiniMax endpoint.

## Policy

Run c1 for real use:

- OpenAI-compatible vLLM on `0.0.0.0:8000`
- `max_model_len=32768`
- `max_num_seqs=1`
- no CPU KV offload
- KV dtype `auto` / FP16-family

c2/c4/c8 and TurboQuant stay research profiles until their larger-context
sustained decode and scheduler behavior are production-safe.

## Install The Service

From the repo:

```bash
cd /home/steve/llm-optimizations
scripts/install-minimax-vllm-service.sh
```

Install and immediately move the current manual server under systemd:

```bash
cd /home/steve/llm-optimizations
scripts/install-minimax-vllm-service.sh --restart
```

The installed unit is:

```text
/etc/systemd/system/minimax-vllm.service
```

The tracked source unit is:

```text
deploy/systemd/minimax-vllm.service
```

## Operate

```bash
systemctl status minimax-vllm.service --no-pager
journalctl -u minimax-vllm.service -f
sudo systemctl restart minimax-vllm.service
sudo systemctl stop minimax-vllm.service
```

Health check:

```bash
scripts/minimax-prod-health.py
```

Expected model report:

```json
{
  "max_model_len": 32768
}
```

Run a small endpoint benchmark:

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
scripts/minimax-prod-benchmark.py \
  --output-json "/mnt/fast-ai/bench-results/minimax-m27-b70-serve/prod-c1-benchmark-${ts}.json"
```

Reference systemd-run result from 2026-05-26:

| Scenario | Prompt tokens | Output tokens | Mean output tok/s after TTFT | Mean TTFT | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `short_decode` | `372` | `512` | `96.82` | `0.227 s` | decode-heavy smoke |
| `prefill_16k` | `18924` | `16` | `77.89` | `13.085 s` | prompt-heavy mid-context |
| `near32k` | `32264` | `64` | `63.91` | `23.336 s` | near-full 32K request |

The near-32K result was accepted by LocalMaxxing as
`cmpm35jsa0003rt01zghtmwip`. Payload and response:

- `../data/localmaxxing-minimax-m27-prod-c1-systemd-near32k-20260526.payload.json`
- `../data/localmaxxing-responses/minimax-m27-prod-c1-systemd-near32k-20260526.response.json`

## Production Notes

Use a queue or proxy in front of this service if more than one user or agent may
call it at the same time. c1 intentionally runs one active generation at a time
because that is the fastest and most reliable path on this host.

For LAN use, restrict access with the firewall or a reverse proxy. vLLM itself
does not provide authentication for this endpoint.

For remote OpenAI-compatible clients, use:

```text
http://<server-lan-ip>:8000/v1
```
