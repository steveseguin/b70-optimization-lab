# Gemma 4 26B Q8 Production Service

This page is the operational recipe for serving Gemma 4 26B A4B Q8 as a
localhost OpenAI-compatible backend on one Intel Arc Pro B70.

## Expected Healthy Outcome

A healthy deployment should look like this:

- `/v1/models` returns model id `gemma4-26b-a4b-q8` with `n_ctx=32768`.
- Short production smoke passes JSON and color-sort checks with
  `cached_tokens=0`.
- Compact text canary passes all rows; the last tracked deployment check passed
  `32/32`.
- 32K service smoke can process the largest current long-context case,
  `lc-24000-late`, as an actual `32571` prompt-token request with
  `cached_tokens=0` and exact JSON retrieval passing.
- Current observed 32K service smoke performance on one B70:
  TTFT about `32.682 s`, approximate prefill about `996.600 tok/s`, and decode
  after TTFT about `115.179 tok/s`.

These numbers are deployment expectations, not a LocalMaxxing short-decode
record claim. The short-decode record remains the fixed realistic-suite
`124.977 tok/s` result documented in `HANDOFF.md` and `reproduce.md`.

## Start Manually

Record/short-decode profile:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19350 GEMMA4_26B_PROFILE=record \
  scripts/serve-gemma4-26b-q8-production.sh
```

Balanced prompt/long-context service profile:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19350 GEMMA4_26B_PROFILE=service \
  scripts/serve-gemma4-26b-q8-production.sh
```

The server listens on `127.0.0.1` by default. Set `HOST=0.0.0.0` only if you
intentionally want to expose llama-server directly; the preferred LAN exposure
pattern is still the repo frontdoor.

## Smoke

```bash
cd /home/steve/llm-optimizations
scripts/gemma4-26b-prod-health.py \
  --base-url http://127.0.0.1:19350 \
  --model gemma4-26b-a4b-q8 \
  --output-json data/gemma4-26b-prod-health-$(date -u +%Y%m%dT%H%M%SZ).json
```

Last tracked smoke: `data/gemma4-26b-prod-health-20260703T002144Z.json`
passed against `GEMMA4_26B_PROFILE=record` on GPU0 / port `19350` with
`cached_tokens=0` on the smoke requests.

Optional fuller text canary:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:19350 \
  --model gemma4-26b-a4b-q8 \
  --repeats 32 \
  --out data/gemma4-26b-prod-canary-$(date -u +%Y%m%dT%H%M%SZ).json
```

Last tracked compact canary:
`data/gemma4-26b-prod-canary-20260703T002151Z.json`, `32/32` rows passed.

## 32K Smoke

The service profile was also tested against the largest long-context suite case:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19350 GEMMA4_26B_PROFILE=service \
  scripts/serve-gemma4-26b-q8-production.sh

python3 scripts/bench-openai-long-context-suite.py \
  --base-url http://127.0.0.1:19350 \
  --model gemma4-26b-a4b-q8 \
  --suite repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json \
  --case-id lc-24000-late \
  --max-tokens 96 \
  --out data/gemma4-26b-prod-service-32k-smoke-$(date -u +%Y%m%dT%H%M%SZ).json
```

Tracked result:
`data/gemma4-26b-prod-service-32k-smoke-20260703T002811Z.json`.
It used `32571` prompt tokens, `cached_tokens=0`, passed exact JSON retrieval,
and measured about `996.600` prompt tok/s plus `115.179` decode tok/s after
TTFT.

## Install Systemd Backend

The tracked unit is:

```text
deploy/systemd/gemma4-26b-q8-llamacpp.service
```

Install and enable it:

```bash
cd /home/steve/llm-optimizations
scripts/install-gemma4-26b-q8-service.sh
```

Start/restart immediately:

```bash
scripts/install-gemma4-26b-q8-service.sh --restart
```

The unit starts only the localhost backend at `127.0.0.1:19350`. It does not
replace the current public `:8000` frontdoor. To expose Gemma 26B through the
LAN endpoint, point the frontdoor/backend profile at
`http://127.0.0.1:19350` after the smoke passes.

## Profile Notes

`record` profile:

- exact current short-decode identity;
- UD-Q8_K_XL target/verifier and Q4_0 MTP draft;
- 32K context, FA on, VMM on;
- `n_max=3`, `n_min=2`, `p_min=0.0475`;
- preferred when reproducing the `124.977 tok/s` strict gate.

`service` profile:

- same target/verifier and MTP safety rules;
- service/prefill knobs from the validated long-context lane;
- preferred when users will send long prompts or care about prompt processing.

Neither profile permits warmed/cache/history speed claims. A production smoke
proves the endpoint is usable; it is not a LocalMaxxing submission.
