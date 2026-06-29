# MiniMax Production C1 Service

This is the recommended production-friendly shape for the current 4x B70
MiniMax endpoint.

LocalMaxxing submission credentials and helper usage are documented in
[localmaxxing.md](localmaxxing.md); keep the API key outside Git.

## Policy

Run c1 for real use:

- no-auth OpenAI-compatible LAN frontdoor on `0.0.0.0:8000`
- localhost-only vLLM backend on `127.0.0.1:18080`
- `max_model_len=32768`
- `max_num_seqs=1`
- no CPU KV offload
- KV dtype `auto` / FP16-family

The frontdoor is intentionally open on the LAN. It does not require a bearer
token. Put it behind a firewall or reverse proxy if the LAN itself is not the
trust boundary.

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
/etc/systemd/system/minimax-openai-frontdoor.service
```

The tracked source unit is:

```text
deploy/systemd/minimax-vllm.service
deploy/systemd/minimax-openai-frontdoor.service
```

## Operate

```bash
systemctl status minimax-vllm.service --no-pager
systemctl status minimax-openai-frontdoor.service --no-pager
journalctl -u minimax-vllm.service -f
journalctl -u minimax-openai-frontdoor.service -f
sudo systemctl restart minimax-vllm.service
sudo systemctl restart minimax-openai-frontdoor.service
sudo systemctl stop minimax-vllm.service
sudo systemctl stop minimax-openai-frontdoor.service
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

Frontdoor status:

```bash
curl http://127.0.0.1:8000/status
```

Expected shape:

```json
{
  "frontdoor": {
    "backend": "http://127.0.0.1:18080",
    "max_active_generations": 1,
    "auth": "none"
  }
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

Frontdoor concurrency smoke after moving vLLM behind localhost:

- two simultaneous `/v1/completions` requests, `128` output tokens each;
- `/status` during the run showed `active_generations=1` and
  `queued_generations=1`;
- both requests returned HTTP `200`;
- individual elapsed times were `1.394 s` and `2.768 s`;
- total wall time was `2.769 s`, confirming serialized generation at the
  frontdoor.

## Production Notes

Use a queue or proxy in front of this service if more than one user or agent may
call it at the same time. The tracked frontdoor does this for the common LAN
case by serializing generation endpoints while allowing health/model requests
through. c1 intentionally runs one active generation at a time because that is
the fastest and most reliable path on this host.

For LAN use, restrict access with the firewall or a reverse proxy if needed.
The default frontdoor does not provide authentication.

For remote OpenAI-compatible clients, use:

```text
http://<server-lan-ip>:8000/v1
```
