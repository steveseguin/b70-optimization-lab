# SC117 Flash-Next IQ3_S: LAN chat service on our own engine

This service hosts `SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF` (IQ3_S, revision `eec4e10a`) on
our corrected two-rank native engine. It serves an OpenAI-style chat endpoint on the LAN, with
MTP speculative decoding turned on. **Status: experimental hosting. It is not quality-qualified.** See
"Fidelity status" below.

## Use

| | |
|---|---|
| LAN URL | `http://192.168.2.44:18160/v1` (also `http://127.0.0.1:18160/v1` on this host) |
| Model id | `sc117-qwen3.8-flash-next-iq3s-ownrt` |
| Endpoints | `POST /v1/chat/completions`, `GET /v1/models`, `GET /health` |
| Auth | none by default; LAN (192.168.2.0/24) and loopback clients only. Put a key in `~/.config/sc117-lan/api_key` before starting to require `Authorization: Bearer <key>`. |

```bash
curl http://192.168.2.44:18160/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain why the sky looks blue."}],"max_tokens":200}'
```

Clients such as Open WebUI or the `openai` SDK: set the base URL to `http://192.168.2.44:18160/v1` and use any API key
string, unless you configured a key.

Start and stop the service through the user unit only. The unit has no `[Install]` section, so it never starts at boot.

```bash
systemctl --user start sc117-lan     # loads on cards 0000:23:00.0 + 0000:47:00.0 (~2 min), self-test, then ready
systemctl --user stop sc117-lan      # finishes the current request, FINISHes both ranks, waits for drain
curl -s http://192.168.2.44:18160/health
journalctl --user -u sc117-lan -n 50
```

The unit file is tracked as [sc117-lan.service](sc117-lan.service). Its installed copy is
`~/.config/systemd/user/sc117-lan.service`. Its settings are `Restart=no`, `KillMode=process`, `SendSIGKILL=no`
and `TimeoutStopSec=infinity`. It uses the same nice 19 and CPU set (0-3, 16-19) as the qualification runs.

## What it does and does not do

- **Serial.** One generation runs at a time. Up to 8 more requests wait in a queue; beyond that the service returns 429.
- **MTP is on for every request.** Every emitted token is the target's argmax. Draft proposals are only verified by
  the target, so they cannot change the output. The real-model evidence is launch-b: target-only and MTP gave
  identical tokens and an identical full target state.
- **Greedy decoding only.** `temperature`, `top_p` and similar parameters are accepted and ignored. Each
  response lists them under `ownrt.ignored_sampling_parameters`.
- **Context: 4096 tokens** (prompt plus output). This is the only admitted configuration for the split-24/24 engine
  with the draft on rank 0. `max_tokens` defaults to 512. A larger request is clamped to whatever room the context has
  left. Device runs have validated up to 512 output tokens. Longer outputs, up to the context limit, use the same
  native loop, but no device run has validated them.
- **The prompt is processed token by token.** No batched prefill exists, so long prompts take noticeably longer
  before the first output.
- **Real streaming (since 2026-10-24 13:38 EDT).** The service build runs with `--token-stream jsonl`: rank 0 appends
  each **target-confirmed** token (never a draft guess) to `confirmed-tokens.jsonl` as soon as it is accepted or corrected. The
  service tails that file and sends SSE text deltas. Deltas hold back an unfinished UTF-8 character and any tail that
  could start a stop string. The final stream must equal `native-result.json` exactly, or the request fails. The
  concatenated deltas always equal the non-streaming answer. First text arrived 0.96 s after the request on a short
  prompt. A non-streaming request sends nothing until the answer is done.
  Long queue waits plus a long generation can therefore exceed a client's timeout (Open WebUI defaults to 300 s).
- **Text only.** Supported roles are system, user and assistant. Images and tools are rejected with HTTP 400.
  Thinking is off by default, which matches the validated template rendering. Pass
  `"chat_template_kwargs":{"enable_thinking":true}` to turn it on. The reasoning then appears in `reasoning_content`.
- **`stop` strings** are applied by truncating the text after generation. They do not stop the engine early.
- **Lifetime: 47 hours per start.** The native engine has a hard deadline of at most 172,800 s from load. The service
  stops gracefully before that deadline and stays stopped. Start it again by hand. Nothing restarts it automatically.

## Safety behavior

- Startup refuses to run outside the unit, or with unsafe unit properties, the wrong nice or CPU set, an
  `igdrcl.config` driver override, or a campaign lane marker present.
- Admission requires all of the following. The kernel GPU-fault list must match the recorded baseline. Neither
  target card may have a holder. MemAvailable must be at least 98.8 GB. Root free space must be at least 27 GB +
  256 MiB. The evidence disk must have at least 2 GiB plus one RESET dump free.
- A passive monitor (`operating/observe.py`, procfs, journal and sudo holder inventory) samples every 3 s.
  The service halts on any of these events:
  - a new xe kernel fault;
  - a boot or DRM topology change;
  - a foreign process on a target card;
  - a rank on the wrong card;
  - a lost rank;
  - MemAvailable below 8 GiB;
  - repeatedly inconclusive observations.

  When it halts, it stops intake, sends the single cooperative stop and waits for both ranks to exit and the target
  cards to drain. Then it writes `incident.json` and exits 1. It sends no kill signals, makes no retries and
  performs no device resets. A halted service stays down until a person looks at the incident.
- When storage falls below a floor, the service refuses new requests with HTTP 507. It does not lower any floor.
- The protected vision server (cards 27:00.0 and 43:00.0) is not touched. Changes to it are only noted.

## Service build (current)

Since 2026-10-24 13:38 EDT the service runs binary `a6da826f…` ([build receipt](../../service-speed/a-reset-stream/build-receipt.json)) through
[adapter2.py](adapter2.py) with `--reset-dump none --finish-dump none --token-stream jsonl`.
- **What it is:** an entry-only rebuild of engine 5926 with three default-off options.
- **What changed:** host code only. Recompiling and relinking the unchanged sources reproduces 5926 byte-for-byte, and
  all 53 device code images of the new binary are byte-identical to 5926's.
- **Device gate:** on its first start the service ran a one-time gate against engine 5926
  ([evidence](evidence/b0-a6da826f58efd2f1.json)). All of these passed:
  - the selftest after RESET: tokens identical, and the full target state byte-identical on both ranks to the launch-b
    physical hashes;
  - the incident prompt, 512 outputs, target-only and MTP: tokens identical to the longer-a run of 5926;
  - the selftest again after three dump-free RESETs: tokens and full state identical.
- **Effect:** RESET now takes about 0.11 s instead of 4.1 s, and no per-request dump is written.

## Storage and retention

Before each request after the first, the native RESET writes about 320 MB of complete engine state (310,364,224
target bytes plus 9,699,332 draft bytes) into the previous request's directory. These dumps are research-grade
evidence that a chat service does not need. **The service retention policy deletes each dump, together with its
`req-NNNNNN` directory, after the next request has run.** At most one dump exists at a time. A one-line summary of
each request is kept in the control `requests.jsonl`. It holds counts, MTP stats and timings, but no prompt or
response text.

Known unbounded growth: native rank 1 appends to `rank1/p92-host.jsonl` in its base directory, at about 155 bytes
per processed position. RESET never moves this file, and it cannot be deleted while open. With about 200 MB of
headroom on the evidence disk, the service starts refusing requests with 507 after roughly 1.3 million positions.
A stop/start of the unit begins a fresh file. Then the old run directory can be removed.

- Control directory (root disk): `~/own-xpu-runtime-results/sc117-lan/run-<UTC>/`, with `current` pointing at the
  newest run. It holds `run.json`, `plan.json`, `monitor.json`, `requests.jsonl`, `selftest-result.json`, rank logs,
  and `terminal.json` or `incident.json`.
- Rank evidence (USB disk): `/mnt/usb-models/own-xpu-runtime-results/sc117-lan/run-<UTC>/`. It holds launch
  metadata, about 13 MB per run after a clean stop. This includes the 9.7 MB draft state that FINISH writes.

## Identity

| | |
|---|---|
| Target | `/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a` (hashes in `../../model-identity.json`) |
| Draft | official Qwen3.8-Flash-Next-FP8 MTP head, `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8` rev `bcd9f01d` |
| Engine | `/mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/gsq-recurrent-f32`, SHA256 `5926a247…51f4`, `--recurrent-f32` and the five GSQ kernel flags |
| Placement | split 24/24, rank 0 on `0000:23:00.0` with the draft, rank 1 on `0000:47:00.0`, context 4096 |
| Adapter | [adapter.py](adapter.py), a copy of the prefix-replay-a generated adapter. [adapter.py.patch](adapter.py.patch) holds the only deltas: lifetime bound, no request cap, service storage forecast. |
| Tokenizer | pinned `tokenizer.json` plus the GGUF chat template, verified by `../../coverage/tokenizer.py` |

Startup self-test: the first two requests after load (fresh state, then RESET plus retention) must each reproduce the launch-b 32-token MTP output exactly
([selftest.json](selftest.json)). That output equals target-only and the independent CPU reference. The service does
not open for requests if the self-test fails.

## Fidelity status (unchanged by this service)

The engine keeps GDN recurrent state and history in F32. Attention KV and ordinary activations, router and expert
outputs, and final logits round to BF16. On the incident prompt it matched the independent CPU reference for the
first 70 outputs. At output 70 it chose token 220 and the CPU chose 264. The native logit gap was 0.375; the CPU
log-probability gap was 0.062. Rounding the final store alone cannot reverse the order (see
`../../recurrent-f32/operating/prefix-replay-a/RESULT.md`).

No measured quality loss has been established, and none has been ruled out. The engine is not a qualified
"no degradation beyond the weight quantization" engine. Treat outputs as experimental. MTP adds no deviation of its
own: target-only and MTP give the same tokens.
