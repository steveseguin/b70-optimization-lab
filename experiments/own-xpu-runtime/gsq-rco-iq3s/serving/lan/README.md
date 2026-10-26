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
- **Context: 4096 tokens** (prompt plus output). This is the only admitted configuration for the configured split engine
  with the draft on rank 0. `max_tokens` defaults to 512. A larger request is clamped to whatever room the context has
  left. Device runs have validated up to 512 output tokens. Longer outputs, up to the context limit, use the same
  native loop, but no device run has validated them.
- **Batched prompt reading.** The configured 32-row batches must pass the full-state comparison against token-by-token reading before use. Long prompts still have a substantial first-token wait.
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

The tracked unit selects engine `51f32b2655cc` (receipt
[../../../engine/receipts/51f32b2655cc.json](../../../engine/receipts/51f32b2655cc.json)), built from the canonical
source tree [../../../engine/](../../../engine/) through [adapter6.py](adapter6.py). Its configuration lives in
[sc117-lan.service](sc117-lan.service); each line there carries the measurement behind it.
A controlled research override may select another receipt. [CURRENT.md](../../../../../CURRENT.md) owns live state; the unit alone does not prove that a build is running or has passed its startup gates.
- **Exact 32-bit mode (owner's choice: quality first).** Activations, router and expert outputs, HC streams and the
  attention KV cache are all F32. The weights are unchanged. The MTP draft keeps its own BF16 arithmetic; it only
  proposes tokens, and the target verifies every token.
- **Gates every new engine passes before it serves.**
  - The full engine state after the self-test equals the pinned F32 record
    ([evidence](evidence/), `f32-state-*.json`; the comparison is split-aware when layers move between cards).
  - The batched prompt reading equals token-by-token reading, full state on both cards (`prefill-*.json`; the gate is
    keyed on the binary and every kernel switch, so a changed choice re-runs it).
  - All 12 answers of the fixed suite are byte-identical to the earlier engines
    ([suite runs](../../service-speed/d-mtp-fp8/suite/)).
  - A continued conversation turn equals a fresh request: tokens, MTP guesses and full state on both cards
    (`continue-*.json`, long and short new suffix).
- **Conversation continuation.** If a request's prompt extends the previous request's prompt and answer exactly, the
  engine keeps its state and reads only the new tokens (rank command 16 moves the output directory; the shared region
  is reset except the draft's two first-step inputs). The API reports the reused tokens as `cached_tokens`. Benchmarks
  must show `cached_tokens=0`. `SC117_CONTINUE=0` disables it.
- **Lookup tables in RAM.** Rank 0 copies the embedding and the 28.8 GB per-layer embedding table into host memory at
  load (55 s). Each token reads 16 rows of it; from the USB disk, new text decoded about 30% slower
  ([note](../../../research/2026-10-25-cold-lookup-reads.md)). `OWNRT_LOOKUP_COPY=0` disables it.
- **Rank output on `/dev/shm`** (`SC117_EVIDENCE_PARENT`): per-token stream appends must not go through ntfs-3g.
- **Configuration** (all in the unit file):
  - `SC117_PREFILL_ROWS=32`: prompt chunks.
  - `SC117_DISPATCH`: non-GEMV kernel choices; QSA select specialised, GDN round2.
  - `OWNRT_DRAFT_PREFIX_ROWS=91392`: the draft scores the first 91,392 token ids.
  - `SC117_TARGET_SPLIT=23`: layers 0–22 on card 0 (with the draft), 23–47 on card 1.
  - `OWNRT_MISS=banks-batch` and `OWNRT_SNAPSHOT_HOST=static`: cheap speculation rollback.
  - `OWNRT_DRAFT_KERNELS`: packet59 draft kernels where faster.
  - `OWNRT_MERGE_CHECKS=1`: one expert status check per layer.
- **Speed (2026-10-26):** B19's retained cold 12-prompt service observation measured 66.21 tok/s median decode, with
  every output id/hash and all MTP hits identical to B18. B18 measured 65.67 and B17 64.01; these are not certified
  benchmarks. A 12.4K-token needle/continuation check passed with 62.35 tok/s fresh decode.
  How each step was found: [speed notes](../../../research/2026-10-25-decode-roofline.md), [rank-0 draft result](../../../research/rank0-lab/RESULT.md);
  what not to retry: [DO-NOT-REPEAT](../../service-speed/DO-NOT-REPEAT.md).

- **Fidelity.** Against our exact CPU reference, the engine agrees at 99.90% of positions on the 12-prompt suite. All 6
  disagreements are near-ties, and their source is still open
  ([result](../../service-speed/e-reference/RESULT-F32.md)). Every speed change since then is byte-identical, so that
  figure still holds.
- The binary and objects are located by the selected build receipt. RAM-backed build paths do not survive reboot; `engine/build.py` rebuilds them
  from the tree.
- `engine/tools/service-cycle.sh` performs one controlled reload for an experiment (an application reload, never a
  host restart) and prints the gate summary.

## Keeper model (opt-in, `SC117_KEEPER=1`; lab 2026-10-26, not yet run on the device)

A second model id, `sc117-qwen3.8-flash-next-iq3s-ownrt-keeper`, serves conversations of any length. Requests for the
plain id are unchanged, and with `SC117_KEEPER=0` (the default) nothing changes at all. [keeper.py](keeper.py) loads
ctxkeeper's Keeper (its recipe `qwen`) as a library from `SC117_KEEPER_LIB`. The model sees a bounded view: the
opening messages, NOTES kept in place by the model itself, and the recent turns. Turns that are cut go verbatim to an
archive under `SC117_KEEPER_DIR` (default `/dev/shm/sc117-keeper`; it counts in the storage checks). The model can search
that archive with a `recall` tool. The service answers those searches itself, and the client never sees them. Every
model call runs in process under the engine lock. An engine fault in any of these calls halts the service, exactly as
it does for a client request.

The engine's session checkpoints carry the cost of the long context. They need `SC117_SESSIONS=1`.

- **Head.** Each conversation's opening (the system block with its tools and the first user message) is parked once by a
  split read and pinned. After each cut, the new view restores the head and reads only the NOTES and the recent turns.
- **Notes.** The in-place notes call runs right after the reply that makes it due, before the engine lock is released.
  It is an exact extension of the live state.
- **Continuation.** Recall rounds and ordinary turns continue the live state. So does the next user turn: the RULES
  recital stays in view.

Settings: `SC117_KEEPER_INPLACE_TOKENS` (15000), `SC117_KEEPER_RESERVE` (512 tokens beside the client's `max_tokens`),
`SC117_KEEPER_PINS` (4 pinned heads), `SC117_KEEPER_MAX_GB` (2), `SC117_KEEPER_MAX_RECALLS` (16). The client's reply is
never shortened below its `max_tokens`. If the view does not fit beside it, the view is cut. A conversation whose newest
messages alone do not fit gets HTTP 400. Session key: the `x-session-affinity` header, or ctxkeeper's fingerprint of
the opening messages. Replies arrive whole at the end (SSE keepalives while the internal calls run). Usage reports the
final call; `ownrt.keeper` lists every internal call (cached and read tokens, prompt seconds, restores). `GET
/keeper/status` shows each conversation's cut count. Device test: [keeper_device_test.py](keeper_device_test.py).

### Pi

1. Copy [pi/models.json](pi/models.json) and [pi/settings.json](pi/settings.json) into `~/.pi/agent/`.
2. Run `pi` (pi-coding-agent 1.2.0). The default model is the keeper id. The plain id
   `sc117-qwen3.8-flash-next-iq3s-ownrt` (64K window, no keeper) is in the same file.

Settings: thinking is off by default (`defaultThinkingLevel`; "medium" turns it on), Pi's own compaction is off,
session-affinity headers are on, and `maxTokens` is 8192.

End-to-end check, 2026-10-26 (pi 1.2.0 in a container, headless `--mode json`, keeper model): Pi fixed a failing
unit test. It ran 6 turns with bash, read and edit tool calls. After the first request read the 1.9K-token head,
every turn continued the cached state and read only 7-214 new tokens. The task took 28 s.

A harder check (engine 718a59eff64f): a planted bug (`nums[-1]` → `nums[0]`) in a copy of ctxkeeper's 1,143-line
`notesdelta.py` failed 2 of 11 tests. Pi ran the tests, read the module and its tests, narrowed the bug with greps and
scripts, and restored the original line exactly. It made 10 tool calls, reached a 22.5K-token context and took 296 s.

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

## Historical commissioning identity

This table records the original commissioning build. Current launch settings and
receipts are in the tracked unit and the live-state note above.

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
