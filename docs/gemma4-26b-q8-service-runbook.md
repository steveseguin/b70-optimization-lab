# Gemma 4 26B Q8 Service Runbook

This is the quick restore guide for the temporary Gemma 4 26B A4B Q8
OpenAI-compatible service. Use it when this host needs a local coding/debugging
endpoint for a few days, then stop it again when the GPUs are needed for other
model tests.

For benchmark history and artifacts, see
`../results/gemma4-26b-a4b-q8-b70/production-quad-service.md`.

## Service Shape

Validated production shape:

- model id: `gemma4-26b-a4b-q8`;
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- engine: local llama.cpp/SYCL backend plus no-auth OpenAI frontdoor;
- public API: `http://<server-lan-ip>:8000/v1`;
- context per active request: `65536` tokens;
- output recommendation: `4096` tokens;
- KV cache dtype: `f16`;
- prompt cache: enabled with `--cache-ram 8192`;
- sticky routing: enabled by `X-Agent-Id`, `X-Session-Id`,
  `X-Conversation-Id`, or JSON fields such as `user` and
  `metadata.agent_id`;
- strict cache affinity: `X-Sticky-Mode: strict`.

Per-GPU validated slot shape:

```text
CTX_SIZE=131072
PARALLEL=2
CACHE_RAM_MIB=8192
```

llama.cpp splits that into two `65536`-token active slots per GPU. Therefore:

```text
1 GPU  -> 2 concurrent generation requests, each up to 64K context
4 GPUs -> 8 concurrent generation requests, each up to 64K context
```

If a future host is memory-tight, the fallback is `CTX_SIZE=65536`,
`PARALLEL=1`, and one active 64K request per GPU. Do not switch to 32K slots
unless the client can reliably route short-context work; the 2026-07-07
`6x32K + 2x64K` fallback was rejected because it kept the same total
concurrency as `8x64K` while reducing context.

## Restore On Four GPUs

This installs and starts the tracked systemd units:

```bash
cd /home/steve/llm-optimizations
git pull --ff-only
sudo bash scripts/install-gemma4-26b-q8-quad-service.sh --start
```

Units:

```text
gemma4-26b-q8-quad-backends.service
gemma4-26b-q8-quad-frontdoor.service
```

The installer stops the older `b70-openai-frontdoor.service`,
`minimax-openai-frontdoor.service`, `b70-vllm-slot.service`,
`minimax-vllm.service`, and single-backend Gemma unit so port `8000` and GPU
memory are not shared accidentally.

Expected frontdoor status:

```bash
curl -fsS http://127.0.0.1:8000/v1/frontdoor/status | jq '{
  ok,
  profile: .client_hints.runtime.profile,
  backend_context_tokens: .frontdoor.backend_context_tokens,
  backend_caps: [.frontdoor.backends[].max_active_generations],
  max_active: .client_hints.recommended.max_concurrent_generation_requests,
  max_strict: .client_hints.recommended.max_strict_affinity_generation_requests,
  active: .frontdoor.active_generations,
  queued: .frontdoor.queued_generations
}'
```

Expected shape:

```json
{
  "profile": "ctx131072-parallel2-cache8192-sticky-router",
  "backend_context_tokens": [65536, 65536, 65536, 65536],
  "backend_caps": [2, 2, 2, 2],
  "max_active": 8,
  "max_strict": 8
}
```

Check each backend:

```bash
for p in 19350 19351 19352 19353; do
  curl -fsS "http://127.0.0.1:$p/props" |
    jq -r '"\(.default_generation_settings.n_ctx) \(.total_slots) \(.model_alias)"' |
    sed "s/^/$p /"
done
```

Expected each line:

```text
19350 65536 2 gemma4-26b-a4b-q8
```

## Run On One GPU Without Installing Units

Use this when only one card is free or when testing on another one-GPU host.
Stop anything already using `:8000`, or set `FRONTDOOR_PORT=8001`.

Terminal 1, backend on GPU 0:

```bash
cd /home/steve/llm-optimizations
GEMMA4_26B_PROFILE=service \
GPU_INDICES="0" \
BASE_PORT=19350 \
CTX_SIZE=131072 \
PARALLEL=2 \
CACHE_RAM_MIB=8192 \
scripts/serve-gemma4-26b-q8-quad-production.sh
```

Terminal 2, frontdoor narrowed to that backend:

```bash
cd /home/steve/llm-optimizations
FRONTDOOR_BACKEND_URL=http://127.0.0.1:19350 \
FRONTDOOR_BACKEND_URLS=http://127.0.0.1:19350 \
FRONTDOOR_BACKEND_CAPACITIES=2 \
FRONTDOOR_BACKEND_CONTEXT_TOKENS=65536 \
FRONTDOOR_MAX_ACTIVE_GENERATIONS=2 \
FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST=65536 \
FRONTDOOR_TOTAL_CONTEXT_TOKENS_PER_BACKEND=131072 \
FRONTDOOR_SLOT_PROFILE=ctx131072-parallel2-cache8192-sticky-router-1gpu \
scripts/run-gemma4-26b-q8-quad-frontdoor.sh
```

Expected client settings for this one-GPU mode:

```text
base_url: http://<server-lan-ip>:8000/v1
model: gemma4-26b-a4b-q8
max concurrent generation requests: 2
max context per request: 65536
recommended max output tokens: 4096
```

## Optional One-GPU Systemd Override

If the one-GPU setup should survive shell exits, install the normal units and
add drop-ins:

```bash
cd /home/steve/llm-optimizations
sudo bash scripts/install-gemma4-26b-q8-quad-service.sh

sudo systemctl edit gemma4-26b-q8-quad-backends.service
```

Backend drop-in:

```ini
[Service]
Environment=GPU_INDICES=0
Environment=CTX_SIZE=131072
Environment=PARALLEL=2
Environment=CACHE_RAM_MIB=8192
```

Then:

```bash
sudo systemctl edit gemma4-26b-q8-quad-frontdoor.service
```

Frontdoor drop-in:

```ini
[Service]
Environment=FRONTDOOR_BACKEND_URL=http://127.0.0.1:19350
Environment=FRONTDOOR_BACKEND_URLS=http://127.0.0.1:19350
Environment=FRONTDOOR_BACKEND_CAPACITIES=2
Environment=FRONTDOOR_BACKEND_CONTEXT_TOKENS=65536
Environment=FRONTDOOR_MAX_ACTIVE_GENERATIONS=2
Environment=FRONTDOOR_SLOT_PROFILE=ctx131072-parallel2-cache8192-sticky-router-1gpu
```

Start:

```bash
sudo systemctl daemon-reload
sudo systemctl disable --now b70-openai-frontdoor.service minimax-openai-frontdoor.service 2>/dev/null || true
sudo systemctl restart gemma4-26b-q8-quad-backends.service
sudo systemctl restart gemma4-26b-q8-quad-frontdoor.service
```

Before returning to the four-GPU default, remove the drop-ins:

```bash
sudo systemctl revert \
  gemma4-26b-q8-quad-backends.service \
  gemma4-26b-q8-quad-frontdoor.service
sudo systemctl daemon-reload
```

`systemctl cat gemma4-26b-q8-quad-backends.service` and
`systemctl cat gemma4-26b-q8-quad-frontdoor.service` should show whether any
drop-ins remain.

## Client Guidance

Tell remote callers to query the frontdoor before choosing limits:

```text
GET http://<server-lan-ip>:8000/status
GET http://<server-lan-ip>:8000/v1/frontdoor/status
```

The JSON advertises the base URL, model id, context limit, concurrency limit,
prompt-cache settings, sticky-routing keys, strict affinity support, and an
example request.

Recommended request headers:

```text
X-Agent-Id: stable-agent-or-session-id
X-Sticky-Mode: strict
```

Use strict sticky mode for long repeated repo/tool prompts where cache reuse is
more important than spilling to another free backend. Omit strict mode when the
client wants maximum throughput and can tolerate losing cache affinity.

If the client can estimate tokens exactly, send:

```text
X-Estimated-Prompt-Tokens: <prompt_tokens_plus_requested_output>
```

The frontdoor rejects exact over-window requests early with HTTP `413` instead
of occupying a backend slot.

Prompt-cache warmup for shared repo/system/tool preambles:

```bash
scripts/warm-gemma4-frontdoor-cache.py \
  --base-url http://127.0.0.1:8000/v1 \
  --agent-count 8 \
  --system-file /path/to/shared-system-prefix.txt
```

Use `--agent-count 2` for one GPU. The helper sends strict sticky headers.

## Validation

Basic health:

```bash
scripts/gemma4-26b-prod-health.py \
  --base-url http://127.0.0.1:8000 \
  --model gemma4-26b-a4b-q8
```

Over-window guard:

```bash
curl -sS -o /tmp/gemma-70k-routing.json -w '%{http_code}\n' \
  -H 'Content-Type: application/json' \
  -H 'X-Estimated-Prompt-Tokens: 70000' \
  -H 'X-Agent-Id: context-guard-test' \
  -d '{"model":"gemma4-26b-a4b-q8","messages":[{"role":"user","content":"Return OK."}],"max_tokens":1,"temperature":0}' \
  http://127.0.0.1:8000/v1/chat/completions
```

Expected: `413`.

Strict sticky routing check:

```bash
before=$(curl -fsS http://127.0.0.1:8000/v1/frontdoor/status |
  jq -c '[.frontdoor.backends[].total_generation_requests]')
for i in 1 2; do
  curl -fsS -o /tmp/gemma-strict-sticky-$i.json \
    -H 'Content-Type: application/json' \
    -H 'X-Agent-Id: strict-sticky-check' \
    -H 'X-Sticky-Mode: strict' \
    -d '{"model":"gemma4-26b-a4b-q8","messages":[{"role":"user","content":"Return OK."}],"max_tokens":1,"temperature":0}' \
    http://127.0.0.1:8000/v1/chat/completions >/dev/null
done
after=$(curl -fsS http://127.0.0.1:8000/v1/frontdoor/status |
  jq -c '[.frontdoor.backends[].total_generation_requests]')
jq -n --argjson before "$before" --argjson after "$after" \
  '{before:$before, after:$after, delta:[range(0;($before|length)) as $i | $after[$i] - $before[$i]]}'
```

Expected: both requests increment the same backend counter, for example
`[2,0,0,0]` on four GPUs or `[2]` on one GPU.

Recent four-GPU validation artifact:

```text
data/gemma4-26b-quad-frontdoor-c8-stream-all64k-recheck-20260708T033139Z.json
```

That run used eight concurrent requests, `160` completion tokens each, and
measured `556.124 tok/s` aggregate wall throughput.

## Stop And Restore Other Services

Stop this temporary Gemma service:

```bash
sudo systemctl disable --now \
  gemma4-26b-q8-quad-frontdoor.service \
  gemma4-26b-q8-quad-backends.service
```

Restore the generic vLLM model-slot frontdoor:

```bash
sudo systemctl enable --now b70-openai-frontdoor.service
scripts/switch-vllm-model-slot.sh status
```

Or switch to a specific slot:

```bash
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

Do not leave two large model services active on the same GPUs unless the goal
is an explicit resource-contention experiment.
