# 2026-07-07 Gemma 4 26B Quad Service Deployment

Objective: temporarily serve Gemma 4 26B A4B Q8 across all four Intel Arc Pro
B70 cards while Qwen optimization work is paused.

Deployed services:

- `gemma4-26b-q8-quad-backends.service`: four localhost llama.cpp replicas.
- `gemma4-26b-q8-quad-frontdoor.service`: no-auth LAN frontdoor on `:8000`.

Runtime shape:

- public endpoint: `http://0.0.0.0:8000/v1`;
- model id: `gemma4-26b-a4b-q8`;
- local backends: `127.0.0.1:19350-19353`;
- one active generation per backend, four active generations total;
- backend profile: `GEMMA4_26B_PROFILE=service`;
- target/verifier: UD-Q8_K_XL target with Q4_0 MTP draft, accepted tokens
  verified by the Q8 target;
- context: `49152` after the follow-up increase from the original 32K
  deployment;
- service knobs: `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048`, FA/VMM enabled.

Validation:

- backend health passed on all four replicas:
  - `data/gemma4-26b-prod-health-gpu0-20260707T2044Z.json`;
  - `data/gemma4-26b-prod-health-gpu1-20260707T2044Z.json`;
  - `data/gemma4-26b-prod-health-gpu2-20260707T2044Z.json`;
  - `data/gemma4-26b-prod-health-gpu3-20260707T2044Z.json`.
- public frontdoor health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-20260707T2044Z.json`.
- four-way frontdoor smoke, 160 output tokens each:
  `data/gemma4-26b-quad-frontdoor-c4-smoke-20260707T2045Z.json`;
  aggregate wall throughput `399.735 tok/s`.
- longer four-way frontdoor smoke, 512 output tokens each:
  `data/gemma4-26b-quad-frontdoor-c4-512-20260707T2046Z.json`;
  aggregate wall throughput `417.888 tok/s`, four requests / `2048` output
  tokens total.
- single-backend decode sample on GPU0:
  `data/gemma4-26b-prod-backend0-singledecode-20260707T2046Z.json`;
  `512` output tokens, `cached_tokens=0`, `164.786 tok/s` after TTFT and
  `133.064 tok/s` wall.

Follow-up context increase:

- changed `gemma4-26b-q8-quad-backends.service` to export
  `CTX_SIZE=49152`;
- all four local backends reported `n_ctx=49152` after restart;
- frontdoor health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx49152-20260707T2057Z.json`;
- per-backend health passed:
  `data/gemma4-26b-prod-health-port19350-ctx49152-20260707T2057Z.json`,
  `data/gemma4-26b-prod-health-port19351-ctx49152-20260707T2057Z.json`,
  `data/gemma4-26b-prod-health-port19352-ctx49152-20260707T2057Z.json`, and
  `data/gemma4-26b-prod-health-port19353-ctx49152-20260707T2057Z.json`;
- long-prompt frontdoor canary passed:
  `data/gemma4-26b-quad-frontdoor-ctx49152-longprompt-canary-20260707T2058Z.json`,
  `43073` prompt tokens, `cached_tokens=0`, expected phrase returned;
- four-way frontdoor smoke after the context bump passed:
  `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx49152-20260707T2059Z.json`,
  aggregate wall throughput `398.503 tok/s`;
- post-bump idle/near-idle `xpu-smi` sample showed roughly `29.5-29.8 GB`
  used per card, `90.4-91.2%` memory utilization.

Operational state after validation:

- `gemma4-26b-q8-quad-backends.service`: active/enabled.
- `gemma4-26b-q8-quad-frontdoor.service`: active/enabled.
- `b70-openai-frontdoor.service`: disabled/inactive to avoid port `8000`
  conflict.
- `b70-vllm-slot.service`, `minimax-vllm.service`, and
  `minimax-openai-frontdoor.service`: inactive.
- `xpu-smi` saw all four B70s. The original 32K deployment used about
  `29.1 GB` per card, roughly `89%` memory utilization.

Restore command when research resumes:

```bash
sudo systemctl disable --now \
  gemma4-26b-q8-quad-frontdoor.service \
  gemma4-26b-q8-quad-backends.service

sudo systemctl enable --now b70-openai-frontdoor.service
```

Then use `scripts/switch-vllm-model-slot.sh` or the model-specific launcher for
the next research target.
