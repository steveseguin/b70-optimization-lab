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

The frontdoor keeps one active generation per backend and four active
generations total. Extra generation requests queue at the frontdoor.

The current temporary deployment uses a `131072` token context per GPU/backend.
This is an increase from the original 32K service profile and keeps one
replica per card. A 120K-token prompt canary pushed the active card to about
`31.97 GB` / `97.9%` memory utilization, so this is the current high-utilization
context target.

## Profile

Backends use the validated Gemma service profile:

```text
GEMMA4_26B_PROFILE=service
CTX_SIZE=131072
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

Latest 128K validation artifacts:

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
