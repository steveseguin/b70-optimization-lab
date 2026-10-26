# SC117 production: long context, engine sessions, ctxkeeper inside the engine (plan, 2026-10-26)

## Owner direction (2026-10-26)

- Get the SC117 model ready for production use. Use more context than the 4K lab setting.
- Make ctxkeeper an integral part of the engine and service, not a proxy.
- Hot-load old sessions from disk without reprocessing them.
- The client is the Pi coding-agent harness (pi 1.2.0, `tools/agentbench/agents/pi`).
- Quality stays lossless: F32 activations and F32 KV. Every change is gated bitwise against the previous engine.

## Facts that set the limits

| Item | Value | Source |
|---|---|---|
| Native context | 262,144 (`max_position_embeddings`; GGUF `context_length`); RoPE `default`, theta 1e7, no YaRN | model config and GGUF metadata |
| Engine admission today | GSQ path refuses any context other than 4096 (`main.cpp` "GSQ initial real context4096 only"); generic bound 32768; RoPE table 32768 positions | `main.cpp` 342, 435, 1400 |
| Attention | 12 of 48 layers full attention (QSA sparse: indexer top-k 2048, pooled keys every 4 positions); 36 Gated DeltaNet layers with fixed state | config |
| KV growth (F32) | rank 0 26.0 KB/position (5 layers + draft), rank 1 33.2 KB/position (7 layers) | arena descriptors |
| Card headroom at 4096 (30 GiB plan cap) | rank 0 3.42 GiB, rank 1 1.18 GiB, so rank 1 caps the 2-card layout near 42K | arena descriptors |
| Prompt reading | about 10 ms per row on the two cards (about 100 tok/s): 30K tokens take about 5 minutes | service notes |
| Session state | about 118 MB fixed (GDN state, conv, PLE history, controls) plus about 59.2 KB per position | session-port review |

## Phases

1. **Chat API for Pi and tools.** Done in commits 3b929faf6 and a5ff69f26 (CPU tests 25/25); live after the next
   service reload.
   - OpenAI tool calls in the model's XML format.
   - Past thinking kept in history; `reasoning_effort`.
   - 64 MiB bodies.
   - `SC117_CONTEXT` plumbing, a per-context F32 oracle and scaled dump forecasts.

2. **32K exact.**
   - Audit the GSQ path for context assumptions (QSA kernels, indexer, RoPE, scratch, index math, prefill, draft,
     snapshot) and lift the 4096 guard.
   - Qualify on spare card 27 with the rank-1 driver, then both ranks:
     - positions below 4096 bitwise identical to the 4K engine (KV prefix rows; tails untouched);
     - long positions agree with the independent CPU reference;
     - the service suite is unchanged at 32K.

3. **Engine sessions (save, restore, append; prefix checkpoints).**
   - Port the packet184 two-card checkpoint: `checkpoint_tp2.hpp` state rules, `checkpoint_format.hpp` manifest/lock,
     `tp2_checkpoint.py` two-phase coordinator.
   - New rank ops 17 STAGE, 18 VERIFY, 19 APPLY next to op 16.
   - Include the coordinator's reverse hidden row; with the draft on rank 0 it lives in the shared map.
   - Park sessions in RAM (`/dev/shm`, bounded LRU) and spill to disk. The root disk sits at its floor, so a session
     store needs its own disk.
   - Gates: coverage, boundary, append across RESET, restore-then-save, shared prefix, tamper refusals, suite through
     restores.

4. **ctxkeeper in the service.**
   - Reuse the Keeper policy, `Archive`, `Session`, `notesdelta.py` and `parking.py` as libraries inside `service.py`.
   - Serve them under a second model id, keyed by Pi's `x-session-affinity` header or the opening-message fingerprint.
   - `recall` is answered server-side.
   - Engine MARK/REWIND (a head mark after the system prompt + tools + first user; a view mark per view) lets notes
     calls, recall rounds and cuts re-read only the new part.
   - An engine fault during a notes call must halt (`BaseException`), never be swallowed.

5. **Beyond 32K toward 262K.**
   - Memory: KV for the extra context on cards 27/43 (attention served where the KV lives) or a 4-way layer placement.
   - Speed: indexer/select cost that grows with context; prompt-reading speed.
   - RoPE table extended past 32768 with the same authority.

## Gates common to every phase

- Live service untouched; lab work only on card 27 with `FilterBdfPath`.
- Service reloads only in windows the owner agrees to.
- Outputs and full state bitwise equal to the previous engine wherever both apply.
- No host reboot, driver reset or power-setting change. A kernel GPU fault halts the work, and also the live service
  (its monitor watches all cards).
