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

The current production profile serves two `65536`-token slots on every GPU:

```text
GPU 0 / 127.0.0.1:19350: two 65536-token slots
GPU 1 / 127.0.0.1:19351: two 65536-token slots
GPU 2 / 127.0.0.1:19352: two 65536-token slots
GPU 3 / 127.0.0.1:19353: two 65536-token slots
```

The frontdoor still estimates prompt plus requested output size so exact
over-window requests can fail before occupying a backend slot. Strict sticky
affinity and prompt-cache routing are available for cache-sensitive agents.

For agent workloads, configure clients for at most `8` concurrent generation
requests. Send a stable per-agent or per-session identifier so the frontdoor can
keep repeated prompts on the same backend and make the prompt cache useful:

```text
X-Agent-Id: bug-agent-0
X-Session-Id: repo-audit-20260707
X-Sticky-Mode: strict
```

If custom headers are hard to set, the frontdoor also accepts sticky routing
keys in JSON fields such as `user`, `session_id`, `conversation_id`,
`metadata.agent_id`, or `metadata.session_id`.

Machine-readable client setup hints are available at:

```text
GET http://<server-lan-ip>:8000/status
GET http://<server-lan-ip>:8000/v1/frontdoor/status
```

The JSON includes the OpenAI-compatible base URL, model name, context limits,
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

Warm a shared prompt prefix for stable agent IDs:

```bash
scripts/warm-gemma4-frontdoor-cache.py \
  --base-url http://127.0.0.1:8000/v1 \
  --agent-count 8 \
  --system-file /path/to/shared-system-prefix.txt
```

The helper sends `X-Sticky-Mode: strict` and warms the default `auto` context
tier unless `--tiers` is provided.

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

Latest all-64K/sticky-router validation artifacts:

- status:
  `data/gemma4-26b-quad-frontdoor-status-all64k-20260708T032625Z.json`;
- health:
  `data/gemma4-26b-prod-health-quad-frontdoor-all64k-20260708T032625Z.json`;
- c8 non-streaming smoke:
  `data/gemma4-26b-quad-frontdoor-c8-nonstream-all64k-20260708T032701Z.json`;
- c8 fixed-output streaming benchmark:
  `data/gemma4-26b-quad-frontdoor-c8-stream-all64k-recheck-20260708T033139Z.json`
  (`8` concurrent requests, `160` completion tokens each,
  `556.124 tok/s` aggregate wall throughput).

Mixed-router experiment artifacts:

- rejected aggressive `4,4,4,2` / 14-slot screen:
  `data/gemma4-26b-quad-frontdoor-c14-smoke-mixed-20260707T2300Z.json`;
  short-pool tail latency made it unsuitable for production;
- rejected `6x32K + 2x64K` fallback:
  it kept the same total concurrency as `8x64K` while reducing context on
  three GPUs, so it was superseded by the all-64K profile;
- mixed-profile c8 smoke:
  `data/gemma4-26b-quad-frontdoor-c8-nonstream-mixed-8slot-20260707T2315Z.json`
  (`8` concurrent requests, `397.072 tok/s` aggregate wall throughput for that
  non-streaming prompt shape).

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
