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

Since 2026-10-24 19:06 EDT the service runs engine `8a76e3cedbe4` (receipt
[../../../engine/receipts/8a76e3cedbe4.json](../../../engine/receipts/8a76e3cedbe4.json)), built from the canonical
source tree [../../../engine/](../../../engine/). It goes through [adapter6.py](adapter6.py) with
`SC117_ACTIVATIONS=f32` and `SC117_PREFILL_ROWS=16`, both set in [sc117-lan.service](sc117-lan.service).
- **Batched prefill.**
  - Prompts are read in 16-row chunks on both cards, with the last two prompt tokens read token by token.
  - A one-time startup gate per binary showed batched and token-by-token runs identical: tokens, MTP guesses and the
    full target state on both cards ([evidence](evidence/prefill-8a76e3cedbe42f7f-rows16.json),
    [result](../../service-speed/b-prefill/RESULT.md)).
  - A 581-token prompt reads in 9.7 s instead of 16.2 s.
  - If the gate fails, requests fall back to token-by-token prefill.
  - The binary and its objects are in `/dev/shm/engine-build-pf10`; a reboot loses them, and `engine/build.py`
    rebuilds them from the tree.
- The token-by-token path of this binary reproduces engine 32654dfb exactly: the same F32 self-test and the same suite
  outputs, checked by the gate.
- **Exact 32-bit mode (owner's choice: quality first).**
  - Activations, router and expert outputs, HC streams and the attention KV cache are all F32. There is no intermediate
    BF16 rounding, and RoPE uses an F32 table.
  - The GDN recurrent state was already F32.
  - The weights are unchanged.
  - The MTP draft keeps its own BF16 arithmetic. It only proposes tokens, and the target verifies every token.
- **Same binary, two modes.** Without `SC117_ACTIVATIONS=f32`, the same binary runs the tuned BF16 kernels. That BF16
  mode has passed the one-time device gate against engine 5926: tokens and full engine state byte-identical
  ([evidence](evidence/)).
- **F32 startup check.** On its first F32 start, the service records the selftest tokens, which are identical from fresh
  state and after RESET, in `evidence/f32-selftest-<binary>.json`. Every later start must reproduce them.
- **Fidelity.** Against our exact CPU reference, the engine agrees at 99.90% of positions on the 12-prompt suite. All 6
  disagreements are near-ties, and their source is still open
  ([result](../../service-speed/e-reference/RESULT-F32.md)).
- **Cost.**
  - Decode median: 23.2 tok/s, against 24.0 in BF16 mode.
  - Memory: rank 0 30.68 GB, rank 1 30.07 GB.
- **Earlier service steps that still apply:**
  - RESET takes 0.11 s instead of 4.1 s;
  - there are no per-request dumps;
  - every target-confirmed token is streamed ([a-reset-stream](../../service-speed/a-reset-stream/)).

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
| Engine | `/mnt/usb-models/own-xpu-runtime-builds/own-engine-32654dfb2fde/sc117-engine` (receipt above), `--recurrent-f32`, the five GSQ kernel flags and `--activations f32`. The original engine is 5926a247…51f4. |
| Placement | split 24/24, rank 0 on `0000:23:00.0` with the draft, rank 1 on `0000:47:00.0`, context 4096 |
| Adapter | [adapter5.py](adapter5.py), the latest of the chain adapter.py → adapter2–5. Each step's delta is in its `.patch` file: lifetime/storage, dump-free reset and streaming, FP8 draft option, engine receipts, activation mode. |
| Tokenizer | pinned `tokenizer.json` plus the GGUF chat template, verified by `../../coverage/tokenizer.py` |

Startup self-test: the first two requests after load (fresh state, then RESET) must produce the same 32 tokens. In BF16
mode, that output must be the launch-b output ([selftest.json](selftest.json)). In F32 mode, it must be the pinned
`evidence/f32-selftest-<binary>.json`. The service does not open for requests if the self-test fails.

## Fidelity status

History: the original engine 5926 kept only the GDN state in F32. Everything else rounded to BF16, and it agreed with
our exact reference at 98.2% of positions on the incident sequence. Every miss was a near-tie, and BF16 rounding
explained them ([RESULT.md](../../service-speed/e-reference/RESULT.md)). The owner then chose full 32-bit precision.

Now, in F32 mode, the engine agrees at 99.90% of positions on the 12-prompt suite. The 6 remaining misses are near-ties
of at most 0.1 logit. F32 summation order and the RoPE formula have been ruled out as their cause, and localization is
open ([RESULT-F32.md](../../service-speed/e-reference/RESULT-F32.md)). MTP adds no deviation of its own, because every
token is target-verified. Treat the service as experimental until the residual is explained.
