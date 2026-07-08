# Gemma 4 26B Q8 Quad Production Service

This is the temporary four-B70 deployment shape for serving Gemma 4 26B A4B Q8
while optimization work is paused.

## Endpoint

Public LAN endpoint:

```text
http://<server-lan-ip>:8000/v1
model: gemma4-26b-a4b-q8
auth: none
```

Local backends:

```text
http://127.0.0.1:19350/v1  GPU 0
http://127.0.0.1:19351/v1  GPU 1
http://127.0.0.1:19352/v1  GPU 2
http://127.0.0.1:19353/v1  GPU 3
```

The frontdoor keeps two active generations per backend and eight active
generations total. Extra generation requests queue at the frontdoor.

The current temporary deployment uses `CTX_SIZE=131072` and `--parallel 2` per
GPU/backend. llama.cpp splits the context across parallel slots, so each of the
two slots on a backend has `65536` tokens of context. This profile keeps 64K
context per concurrent request and serves two active requests per card.

For agent workloads, configure clients for at most `8` concurrent generation
requests. Send a stable per-agent or per-session identifier so the frontdoor can
keep repeated prompts on the same backend and make the prompt cache useful:

```text
X-Agent-Id: bug-agent-0
X-Session-Id: repo-audit-20260707
```

If custom headers are hard to set, the frontdoor also accepts sticky routing
keys in JSON fields such as `user`, `session_id`, `conversation_id`,
`metadata.agent_id`, or `metadata.session_id`.

Machine-readable client setup hints are available at:

```text
GET http://<server-lan-ip>:8000/status
GET http://<server-lan-ip>:8000/v1/frontdoor/status
```

The JSON includes the OpenAI-compatible base URL, model name, context and
concurrency limits, prompt-cache settings, sticky-routing keys, and an example
chat-completions request.

## Profile

Backends use the validated Gemma service profile:

```text
GEMMA4_26B_PROFILE=service
CTX_SIZE=131072
PARALLEL=2
CACHE_RAM_MIB=8192
BATCH_SIZE=2048
UBATCH_SIZE=1024
FLASH_ATTN=on
GGML_SYCL_ENABLE_VMM=1
target/verifier: gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
draft: gemma-4-26B-A4B-it-Q4_0-MTP.gguf
spec: n_max=3, n_min=2, p_min=0.0475
```

This favors production prompt/long-context behavior. The short-decode record
profile remains documented separately in `reproduce.md`.

## Install And Start

```bash
cd /home/steve/llm-optimizations
sudo bash scripts/install-gemma4-26b-q8-quad-service.sh --start
```

Installed units:

```text
gemma4-26b-q8-quad-backends.service
gemma4-26b-q8-quad-frontdoor.service
```

The install/start helper disables the older `b70-openai-frontdoor.service` and
`minimax-openai-frontdoor.service` so they do not compete for port `8000`.

## Check Health

```bash
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/v1/models
scripts/gemma4-26b-prod-health.py \
  --base-url http://127.0.0.1:8000 \
  --model gemma4-26b-a4b-q8
```

Latest 128K-total/parallel-2 validation artifacts:

- `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-p2-20260707T2139Z.json`;
- `data/gemma4-26b-prod-health-port19350-ctx131072-p2-20260707T2139Z.json`;
- `data/gemma4-26b-prod-health-port19351-ctx131072-p2-20260707T2139Z.json`;
- `data/gemma4-26b-prod-health-port19352-ctx131072-p2-20260707T2139Z.json`;
- `data/gemma4-26b-prod-health-port19353-ctx131072-p2-20260707T2139Z.json`;
- `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx131072-p2-20260707T2140Z.json`
  (`8` concurrent requests, two `65536`-token slots per backend,
  `553.565 tok/s` aggregate wall throughput);
- `data/gemma4-26b-quad-frontdoor-c8-512-ctx131072-p2-20260707T2141Z.json`
  (`8` concurrent requests, `568.059 tok/s` aggregate wall throughput).
- `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-p2-cache8192-sticky-20260707T2231Z.json`
  confirms the cache/sticky frontdoor profile is healthy.
- `data/gemma4-26b-quad-frontdoor-cache-sticky-probe-20260707T2231Z.json`
  repeated a `12029` prompt-token request with the same `X-Agent-Id`; the
  second request reported `12028` cached tokens and fell from `7.827s` to
  `0.102s`.
- `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx131072-p2-cache8192-sticky-20260707T2229Z.json`
  (`8` concurrent requests, `574.527 tok/s` aggregate wall throughput).
- `data/gemma4-26b-quad-frontdoor-c8-512-ctx131072-p2-cache8192-sticky-20260707T2228Z.json`
  (`8` concurrent requests, `550.934 tok/s` aggregate wall throughput).

Earlier 64K-total/parallel-2 validation artifacts:

- `data/gemma4-26b-prod-health-quad-frontdoor-ctx65536-p2-20260707T2132Z.json`;
- `data/gemma4-26b-prod-health-port19350-ctx65536-p2-20260707T2132Z.json`;
- `data/gemma4-26b-prod-health-port19351-ctx65536-p2-20260707T2132Z.json`;
- `data/gemma4-26b-prod-health-port19352-ctx65536-p2-20260707T2132Z.json`;
- `data/gemma4-26b-prod-health-port19353-ctx65536-p2-20260707T2132Z.json`;
- `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx65536-p1-20260707T2130Z.json`
  (`4` concurrent requests, `408.062 tok/s` aggregate wall throughput);
- `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx65536-p2-20260707T2133Z.json`
  (`8` concurrent requests, `554.136 tok/s` aggregate wall throughput);
- `data/gemma4-26b-quad-frontdoor-c8-512-ctx65536-p2-20260707T2134Z.json`
  (`8` concurrent requests, `568.080 tok/s` aggregate wall throughput).

Earlier 128K validation artifacts:

- `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-20260707T2108Z.json`;
- `data/gemma4-26b-prod-health-port19350-ctx131072-20260707T2108Z.json`;
- `data/gemma4-26b-prod-health-port19351-ctx131072-20260707T2108Z.json`;
- `data/gemma4-26b-prod-health-port19352-ctx131072-20260707T2108Z.json`;
- `data/gemma4-26b-prod-health-port19353-ctx131072-20260707T2108Z.json`;
- `data/gemma4-26b-quad-frontdoor-ctx131072-chat-longprompt-canary-20260707T2114Z.json`
  (`120060` prompt tokens, `cached_tokens=0`, marker returned);
- `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx131072-20260707T2118Z.json`
  (`4` concurrent requests, `394.492 tok/s` aggregate wall throughput).

Earlier 49K validation artifacts:

- `data/gemma4-26b-prod-health-quad-frontdoor-ctx49152-20260707T2057Z.json`;
- `data/gemma4-26b-quad-frontdoor-ctx49152-longprompt-canary-20260707T2058Z.json`
  (`43073` prompt tokens, `cached_tokens=0`, retrieval passed);
- `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx49152-20260707T2059Z.json`
  (`4` concurrent requests, `398.503 tok/s` aggregate wall throughput).

Useful logs:

```bash
journalctl -u gemma4-26b-q8-quad-backends.service -f
journalctl -u gemma4-26b-q8-quad-frontdoor.service -f
ls -t /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/replica-gpu*-port1935*.log
```

## Stop Or Restore The Previous Slot Frontdoor

```bash
sudo systemctl disable --now \
  gemma4-26b-q8-quad-frontdoor.service \
  gemma4-26b-q8-quad-backends.service

sudo systemctl enable --now b70-openai-frontdoor.service
```

If switching to a vLLM model slot, use `scripts/switch-vllm-model-slot.sh`
after stopping the Gemma quad services.
