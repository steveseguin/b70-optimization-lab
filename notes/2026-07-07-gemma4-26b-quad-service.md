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
- two active generations per backend, eight active generations total;
- backend profile: `GEMMA4_26B_PROFILE=service`;
- target/verifier: UD-Q8_K_XL target with Q4_0 MTP draft, accepted tokens
  verified by the Q8 target;
- context: `131072` per backend with `PARALLEL=2`; llama.cpp splits this into
  two `65536`-token slots per backend;
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

Second context increase:

- changed `gemma4-26b-q8-quad-backends.service` to export
  `CTX_SIZE=65536`;
- all four local backends restarted cleanly and health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx65536-20260707T2103Z.json`,
  `data/gemma4-26b-prod-health-port19350-ctx65536-20260707T2103Z.json`,
  `data/gemma4-26b-prod-health-port19351-ctx65536-20260707T2103Z.json`,
  `data/gemma4-26b-prod-health-port19352-ctx65536-20260707T2103Z.json`, and
  `data/gemma4-26b-prod-health-port19353-ctx65536-20260707T2103Z.json`;
- idle/near-idle `xpu-smi` sample showed roughly `29.9 GB` used per card,
  `91.6-91.7%` memory utilization.

Final high-context increase for the temporary service:

- changed `gemma4-26b-q8-quad-backends.service` to export
  `CTX_SIZE=131072`;
- process launch arguments include `-c 131072` for all four replicas, and the
  backend logs show `new slot, n_ctx = 131072`;
- idle/near-idle `xpu-smi` sample after restart showed roughly `31.67-31.69 GB`
  used per card, `96.97-97.05%` memory utilization;
- while a 120K-token prompt canary was active, the busy card peaked around
  `31.97 GB`, `97.89%` memory utilization;
- frontdoor and per-backend health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-20260707T2108Z.json`,
  `data/gemma4-26b-prod-health-port19350-ctx131072-20260707T2108Z.json`,
  `data/gemma4-26b-prod-health-port19351-ctx131072-20260707T2108Z.json`,
  `data/gemma4-26b-prod-health-port19352-ctx131072-20260707T2108Z.json`, and
  `data/gemma4-26b-prod-health-port19353-ctx131072-20260707T2108Z.json`;
- raw completions capacity canary completed without truncation:
  `data/gemma4-26b-quad-frontdoor-ctx131072-longprompt-canary-20260707T2109Z.json`,
  `120067` prompt tokens, `cached_tokens=0`, HTTP 200, server log
  `truncated = 0`; the content assertion is not counted because the raw
  completion prompt ended with the marker and the model completed it with a
  period;
- chat long-prompt canary passed:
  `data/gemma4-26b-quad-frontdoor-ctx131072-chat-longprompt-canary-20260707T2114Z.json`,
  `120060` prompt tokens, `cached_tokens=0`, expected marker returned;
- four-way frontdoor smoke at 128K passed:
  `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx131072-20260707T2118Z.json`,
  aggregate wall throughput `394.492 tok/s`;
- MTP startup logs still report the single-sequence fast path requirements
  (`requires shared memory + single seq`), so doubling per-GPU concurrency is a
  separate experiment and not part of this production config.

Concurrency retest with 64K total context:

- changed `gemma4-26b-q8-quad-backends.service` to export
  `CTX_SIZE=65536` and `PARALLEL=2`;
- changed the quad frontdoor defaults to `FRONTDOOR_MAX_ACTIVE_GENERATIONS=8`
  and backend capacities `2,2,2,2`;
- process launch arguments include `-c 65536 --parallel 2` for all four
  replicas;
- llama.cpp initialized `n_slots = 2` and reported `new slot, n_ctx = 32768`
  for each slot; the `65536` backend context is split across the two slots;
- MTP fast-path knobs changed as expected for multi-slot serving:
  `defer_target_h_nextn=0` and `draft_direct_argmax_unroll=1`, because the
  faster values require shared memory plus single-sequence execution;
- 64K/parallel-1 comparison run:
  `data/gemma4-26b-quad-frontdoor-c4-smoke-ctx65536-p1-20260707T2130Z.json`,
  four active requests, aggregate wall throughput `408.062 tok/s`;
- frontdoor and per-backend health passed for 64K/parallel-2:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx65536-p2-20260707T2132Z.json`,
  `data/gemma4-26b-prod-health-port19350-ctx65536-p2-20260707T2132Z.json`,
  `data/gemma4-26b-prod-health-port19351-ctx65536-p2-20260707T2132Z.json`,
  `data/gemma4-26b-prod-health-port19352-ctx65536-p2-20260707T2132Z.json`, and
  `data/gemma4-26b-prod-health-port19353-ctx65536-p2-20260707T2132Z.json`;
- 8-way frontdoor smoke passed:
  `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx65536-p2-20260707T2133Z.json`,
  aggregate wall throughput `554.136 tok/s`, roughly `35.8%` above the
  64K/parallel-1 four-way comparison;
- 8-way 512-token frontdoor smoke passed:
  `data/gemma4-26b-quad-frontdoor-c8-512-ctx65536-p2-20260707T2134Z.json`,
  aggregate wall throughput `568.080 tok/s` over `4096` output tokens;
- post-load status showed both services active, zero queued generations, and
  `xpu-smi` around `30.31-30.34 GB` used per card, `92.83-92.91%` memory
  utilization.

Corrected 64K-per-slot concurrency profile:

- corrected the backend context to `CTX_SIZE=131072` with `PARALLEL=2`;
- process launch arguments include `-c 131072 --parallel 2` for all four
  replicas;
- llama.cpp initialized `n_slots = 2` and reported `new slot, n_ctx = 65536`
  for each slot, which is the intended two 64K sessions per GPU;
- frontdoor and per-backend health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-p2-20260707T2139Z.json`,
  `data/gemma4-26b-prod-health-port19350-ctx131072-p2-20260707T2139Z.json`,
  `data/gemma4-26b-prod-health-port19351-ctx131072-p2-20260707T2139Z.json`,
  `data/gemma4-26b-prod-health-port19352-ctx131072-p2-20260707T2139Z.json`, and
  `data/gemma4-26b-prod-health-port19353-ctx131072-p2-20260707T2139Z.json`;
- 8-way frontdoor smoke passed:
  `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx131072-p2-20260707T2140Z.json`,
  aggregate wall throughput `553.565 tok/s`;
- 8-way 512-token frontdoor smoke passed:
  `data/gemma4-26b-quad-frontdoor-c8-512-ctx131072-p2-20260707T2141Z.json`,
  aggregate wall throughput `568.059 tok/s` over `4096` output tokens;
- post-load status showed both services active, zero queued generations, and
  `xpu-smi` around `31.85-31.88 GB` used per card, `97.53-97.61%` memory
  utilization;
- throughput is effectively unchanged from the accidental 32K-per-slot profile
  on short decode, but the corrected profile provides the intended 64K context
  per active request.

Prompt-cache and sticky-routing production update:

- enabled `CACHE_RAM_MIB=8192`, which starts llama.cpp with
  `--cache-ram 8192`;
- startup logs confirmed `prompt cache is enabled, size limit: 8192 MiB` and
  `idle slots will be saved to prompt cache upon starting a new task`;
- enabled frontdoor sticky routing using headers `X-Agent-Id`, `X-Session-Id`,
  and `X-Conversation-Id`, plus JSON fields `user`, `session_id`,
  `conversation_id`, `metadata.agent_id`, and `metadata.session_id`;
- frontdoor health passed:
  `data/gemma4-26b-prod-health-quad-frontdoor-ctx131072-p2-cache8192-sticky-20260707T2231Z.json`;
- repeated sticky prompt probe passed:
  `data/gemma4-26b-quad-frontdoor-cache-sticky-probe-20260707T2231Z.json`;
  a repeated `12029` prompt-token request with the same `X-Agent-Id` went from
  `7.827s`, `cached_tokens=0`, to `0.102s`, `cached_tokens=12028`;
- eight distinct sticky agent IDs completed successfully and the frontdoor
  stayed balanced across the four backends;
- post-cache throughput smoke:
  `data/gemma4-26b-quad-frontdoor-c8-smoke-ctx131072-p2-cache8192-sticky-20260707T2229Z.json`,
  aggregate wall throughput `574.527 tok/s`;
- post-cache 512-token smoke:
  `data/gemma4-26b-quad-frontdoor-c8-512-ctx131072-p2-cache8192-sticky-20260707T2228Z.json`,
  aggregate wall throughput `550.934 tok/s`;
- operational guidance for the code/tool-agent app: set max active generation
  requests to `8`, and send a stable sticky key per agent or session.
- machine-readable client setup hints are exposed at `/status` and
  `/v1/frontdoor/status`; the JSON includes API paths, model id, context and
  concurrency limits, prompt-cache settings, sticky-routing keys, runtime
  details, and an example request.

Mixed-context router update:

- changed the temporary quad backend shape from four identical `64K x 2`
  replicas to a mixed fleet:
  - an initial `GPU0-2: PARALLEL=4` attempt exposed a pathological 14-way
    smoke result: the 64K backend completed quickly, but the 12 short-pool
    requests took roughly `126-161s`; that shape is not the production default;
  - a follow-up `GPU0-2: PARALLEL=3` attempt was also rejected: an 11-way
    non-streaming smoke drained most requests quickly but left a 3-request
    short-backend tail active for several minutes;
  - GPU0-2 now use `CTX_SIZE=65536`, `PARALLEL=2`, two `32768`-token slots
    each;
  - GPU3 uses `CTX_SIZE=131072`, `PARALLEL=2`, two `65536`-token slots;
- public endpoint contract remains `65536` max context; the frontdoor estimates
  prompt plus requested output size and routes `<=32768` requests to the dense
  32K pool while sending larger requests to the 64K backend;
- frontend capacity remains `8` active generation requests total
  (`2,2,2,2` by backend), now split as six 32K slots and two 64K slots;
- added `X-Sticky-Mode: strict` so cache-sensitive agents can wait for their
  sticky backend instead of spilling and losing prompt-cache reuse;
- added `Retry-After` on queue-timeout responses and a `413` guard when an
  exact client token hint exceeds available context windows;
- added `scripts/warm-gemma4-frontdoor-cache.py` to warm stable agent IDs
  across short and long context tiers.

Final mixed-profile validation:

- active profile:
  `mixed-6x32k-2x64k-cache8192-sticky`;
- status artifact:
  `data/gemma4-26b-quad-frontdoor-status-mixed-8slot-20260707T2315Z.json`;
- health artifact:
  `data/gemma4-26b-prod-health-quad-frontdoor-mixed-8slot-20260707T2315Z.json`;
- routing probe passed: short exact hint routed to a 32K backend, long exact
  hint routed to the 64K backend, and an exact over-window hint returned
  `413 context_window_exceeded`;
- c8 non-streaming smoke:
  `data/gemma4-26b-quad-frontdoor-c8-nonstream-mixed-8slot-20260707T2315Z.json`,
  aggregate wall throughput `397.072 tok/s` for this prompt shape;
- final service state after validation: both Gemma units active/running with
  `NRestarts=0`, frontdoor active `0`, queued `0`.

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
