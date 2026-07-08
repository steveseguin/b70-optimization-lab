# Gemma 4 26B A4B Q8 Handoff

Last updated: 2026-07-03

This is the bookmark for the Gemma 4 26B A4B Q8 work on Intel Arc Pro B70.
Read this before resuming optimization, deploying a Gemma 26B endpoint, or
switching away and coming back later.

## Current Status

Gemma 26B is no longer an unstructured active search. It is captured as a
usable one-B70 llama.cpp service profile plus a research frontier.

Best strict short-decode result:

- `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- evidence:
  `../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- LocalMaxxing ID: `cmr1u77na01k2ld01kalwzs1e`;
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: Q4_0 MTP draft only, with accepted tokens verified by the Q8 target;
- no prompt/KV/response/cache/history reuse, `cached_tokens=0` for every fixed
  realistic-suite request.

Latest same-recipe documentation-pass rerun:

- `120.92334534956485 tok/s`;
- evidence:
  `../../data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`;
- valid support for the recipe, not a replacement for the `124.977` high.

Variance is real. The 2026-07-02 analysis concluded that `120` versus `125`
is mostly output path/content/MTP acceptance variance, not recipe drift. See:

- `../../notes/2026-07-02-gemma-125-rerun-variance-diagnostic.md`;
- `reliability-protocol.md`;
- `validity-gates.md`.

## Production Serving

The persistent backend launcher is:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19350 GEMMA4_26B_PROFILE=record \
  scripts/serve-gemma4-26b-q8-production.sh
```

It serves an OpenAI-compatible llama-server backend on:

```text
http://127.0.0.1:19350/v1
model id: gemma4-26b-a4b-q8
```

Profiles:

- `GEMMA4_26B_PROFILE=record`: conservative default. This is the strict
  short-decode record identity: 32K context, FA on, VMM on, UD-Q8_K_XL target,
  Q4_0 MTP draft, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`.
- `GEMMA4_26B_PROFILE=service`: 32K prompt/long-context service profile. It
  keeps the same Q8 target and verifier rules, but enables the validated
  service/prefill knobs (`LLAMA_PREFILL_UBATCH_SIZE=2048`, GQA8 ncols2, SWA
  left-bound, KQ register/broadcast). Use this when prompt processing and
  long-context behavior matter more than reproducing the exact short-decode
  record identity.

Tracked service artifacts:

- `../../scripts/serve-gemma4-26b-q8-production.sh`;
- `../../scripts/serve-gemma4-26b-q8-quad-production.sh`;
- `../../scripts/run-gemma4-26b-q8-quad-frontdoor.sh`;
- `../../scripts/gemma4-26b-prod-health.py`;
- `../../deploy/systemd/gemma4-26b-q8-llamacpp.service`;
- `../../deploy/systemd/gemma4-26b-q8-quad-backends.service`;
- `../../deploy/systemd/gemma4-26b-q8-quad-frontdoor.service`;
- `../../scripts/install-gemma4-26b-q8-service.sh`;
- `../../scripts/install-gemma4-26b-q8-quad-service.sh`;
- `production-service.md`;
- `production-quad-service.md`.

Temporary quad deployment on 2026-07-07:

- public no-auth LAN endpoint: `http://0.0.0.0:8000/v1`;
- four local service-profile replicas on `127.0.0.1:19350-19353`;
- current backend context: `131072` tokens with `--parallel 2`; llama.cpp
  splits this into two `65536`-token slots per backend;
- two active generations per backend, eight active generations total;
- prompt cache enabled with `--cache-ram 8192`;
- frontdoor sticky routing enabled by `X-Agent-Id`, `X-Session-Id`,
  `X-Conversation-Id`, or JSON fields such as `user` / `metadata.agent_id`;
- health passed on all four backends and the frontdoor;
- c4/512 frontdoor smoke produced `417.888 tok/s` aggregate wall throughput;
- 128K c4/160 frontdoor smoke produced `394.492 tok/s` aggregate wall
  throughput, and a `120060` prompt-token chat canary passed with
  `cached_tokens=0`;
- latest 64K/parallel-1 comparison run produced `408.062 tok/s` aggregate wall
  throughput with four active requests;
- corrected 64K-per-slot / parallel-2 8-way run produced `553.565 tok/s`
  aggregate wall throughput at 160 output tokens and `568.059 tok/s` at 512
  output tokens;
- observed memory at 64K-per-slot / parallel-2 after load was about
  `31.85-31.88 GB` per card, `97.53-97.61%` utilization;
- multi-slot serving disables the single-sequence MTP fast knobs; the aggregate
  throughput still improved, but per-request throughput dropped to roughly
  `73 tok/s` in the 8-way runs;
- cache/sticky probe repeated a `12029` prompt-token request with the same
  `X-Agent-Id`; the second request reported `12028` cached tokens and fell from
  `7.827s` to `0.102s`;
- advise the client app to use max concurrency `8` for generation requests and
  send stable per-agent/per-session sticky identifiers;
- remote clients can discover setup hints from `/status` or
  `/v1/frontdoor/status`;
- operational note:
  `../../notes/2026-07-07-gemma4-26b-quad-service.md`.

Smoke status on 2026-07-03:

- manual record-profile backend started on GPU0 at
  `http://127.0.0.1:19350/v1`;
- `/v1/models` reported `gemma4-26b-a4b-q8` with `n_ctx=32768`;
- production smoke passed JSON and color-sort checks with `cached_tokens=0`:
  `../../data/gemma4-26b-prod-health-20260703T002144Z.json`;
- compact Gemma text canary passed `32/32` rows:
  `../../data/gemma4-26b-prod-canary-20260703T002151Z.json`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/replica-gpu0-port19350-20260703T002112Z.log`;
- the manual smoke server was stopped afterward so GPU0 is free for the next
  model.

32K service-profile smoke on 2026-07-03:

- manual `GEMMA4_26B_PROFILE=service` backend started on GPU0 at
  `http://127.0.0.1:19350/v1`;
- `/v1/models` reported `n_ctx=32768`;
- largest long-context suite case `lc-24000-late` produced an actual
  `32571` prompt-token request plus `76` generated tokens;
- exact JSON retrieval validation passed, `cached_tokens=0`, prompt was unique;
- measured TTFT `32.682 s`, approximate prefill `996.600 tok/s`, decode after
  TTFT `115.179 tok/s`;
- LocalMaxxing service/prompt-processing result:
  `cmr47ivql0045nv011pfdjlaa` (not the short-decode headline);
- evidence:
  `../../data/gemma4-26b-prod-service-32k-smoke-20260703T002811Z.json`;
- payload/response:
  `../../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-service-32k-20260703.payload.json`
  and
  `../../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-service-32k-20260703.submit.log`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/replica-gpu0-port19350-20260703T002742Z.log`;
- the manual 32K smoke server was stopped afterward.

The systemd unit is localhost-only on port `19350`. It does not rewire the
public `:8000` frontdoor. If Gemma 26B should become the public LAN model,
point the frontdoor at `http://127.0.0.1:19350` after the backend smoke passes.

Smoke a running backend:

```bash
cd /home/steve/llm-optimizations
scripts/gemma4-26b-prod-health.py \
  --base-url http://127.0.0.1:19350 \
  --model gemma4-26b-a4b-q8 \
  --output-json data/gemma4-26b-prod-health-$(date -u +%Y%m%dT%H%M%SZ).json
```

Use the fuller canary when validating after a source/runtime change:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:19350 \
  --model gemma4-26b-a4b-q8 \
  --repeats 32 \
  --out data/gemma4-26b-prod-canary-$(date -u +%Y%m%dT%H%M%SZ).json
```

## Reproduction And Validation

Strict record reproduction:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19350 \
  LABEL=gemma4-q8-gpu0-125repro-$(date -u +%Y%m%dT%H%M%SZ) \
  bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

Production/service smoke is not a LocalMaxxing claim. Promote a result only
through the fixed realistic final gate:

- each fixed prompt once as a cold first response;
- `cached_tokens=0` on every request;
- no prompt/KV cache reuse, checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts;
- same target model and quantization;
- MTP/speculation allowed only with accepted tokens verified by the Q8 target;
- primary metric: median generated-token tok/s for tokens 1-100 after TTFT.

For close changes near the current record, single runs are not enough. Use
paired same-window A/B plus no-spec calibration from `reliability-protocol.md`.

## What Is Left To Improve

Short-decode has diminishing returns from config sweeps. The obvious flag
neighborhoods are mostly exhausted. Expect little reliable gain from another
round of `p_min`, `n_max`, unroll, draft-quant, rowpack, or generic SYCL flag
roulette.

Most plausible remaining short-decode upside:

1. Exact verifier LM-head cost reduction that is not row-by-row serial.
2. A mathematically safe candidate-vs-max verifier certificate that avoids
   full-vocab work where possible.
3. A head-only or bonus-token verifier path that preserves exact target
   verification and does not break the bonus pipeline.
4. MoE selected-down/router kernel reductions beyond the tested VDR2/top8/
   rowpack/direct variants.

Prompt-processing and long-context still have more practical service value.
The best remaining area is Gemma global FlashAttention for `DKQ=576`, `DV=512`
and GQA8/global layer shapes. Existing service wins are small but real; keep
short-decode record validation separate from long-context service validation.

Estimated remaining "meat on the bones":

- short-decode config-only: low, likely `0-3%` and hard to prove;
- short-decode source design: medium, but requires real verifier/MoE kernel
  work;
- prompt/long-context service: medium, likely more useful for production than
  another `+1%` record attempt;
- production polish: high leverage if this model will be served often
  (systemd/frontdoor wiring, soak tests, model-slot integration).

## Do Not Reopen Without New Evidence

- Q8_0 target substitution as a "same quality" result. The promoted lane is
  UD-Q8_K_XL target/verifier.
- INT4 target downgrade for this Q8 headline.
- warmed n-gram/history/cache/prefix/context-checkpoint claims.
- Row-by-row accept-prefix verifier variants.
- `cudagraph_copy_inputs`, global sync, or broad runtime sync-style fixes from
  the Qwen graph lane as a Gemma shortcut.
- Static PB1/right-bound/vecdispatch/no-KQ-LSM/skipbarrier repeats for the
  service FlashAttention lane unless a new kernel change makes them relevant.

## Resume Checklist

When returning to Gemma after another model:

1. Read this file, then `README.md`, `reproduce.md`, `research-plan.md`, and
   `validity-gates.md`.
2. Run `git status --short --branch` and confirm there is one active workspace:
   `/home/steve/llm-optimizations`.
3. Smoke the production backend with `scripts/serve-gemma4-26b-q8-production.sh`
   and `scripts/gemma4-26b-prod-health.py`.
4. If optimizing short decode, first reproduce the record wrapper or a compact
   strict gate. Do not compare against historical highs without same-window
   controls.
5. If optimizing prompt/long-context, use the long-context service gate and
   then rerun the short-decode guard to prove no regression.
6. Preserve every meaningful patch and result in `patches/`, `experiments/`,
   `data/`, and `notes/` before moving on.
