# Flash-Next TP4 eager MTP0 fixed-vision attempt 9 preregistration

Date: 2026-08-28

Attempt 9 is a bounded retry after exact attempt-8 evidence established a
pre-admission initial-memory stop with no evidence lifecycle, card/collective
work, launcher, model load, client, request, or result. After the full frozen
900-second user-manager stability window and external `sync`/drop-caches step,
attempt 8 measured 111,788,592 KiB MemAvailable and 6,297,564 KiB SwapFree.
Its supervisor exited 1 with `FAIL: less than 108 GiB host memory is available`.

The sole treatment is administrative: lower the one-time initial MemAvailable
admission floor by 3 GiB, from 113,246,208 KiB (108 GiB) to 110,100,480 KiB
(105 GiB). Clean post-graph idle observations are around 106 GiB, while prior
successful eager loading retained about 29 GiB MemAvailable. The active-run
stop floors remain exactly 10 GiB MemAvailable and 5 GiB SwapFree; the separate
initial 6-GiB SwapFree admission gate also remains unchanged. This changes no
serving/performance path and makes no performance claim.

Every model and serving identity otherwise remains frozen: current model
revision and staged runtime, TP4/EP4, eager MTP0, selective UVA placement, KV
cache, max-model-len 512, one-image/video-zero modality limit, zero processor
cache, encoder TP weights, same-boot text recovery, seven semantic cases, nine
fixed vision requests, health checks, timeouts, classifier v3 receipts,
cleanup, and the Grade-C maximum. The supervisor hash-binds and structurally
validates the finalized attempt-8 no-work closeout before any other admission.

Fresh administrative identities are:

- attempt 9 and state prefix `/tmp/q38-mtp0-current-vision-a9`;
- port `19688`;
- fresh attempt-9 run, supervisor-evidence, and cache paths;
- short compile/RPC roots `/tmp/q38v-a9-c` and `/tmp/q38v-a9-r`.

The UUID-derived RPC path remains exactly 51 bytes against the 107-byte limit.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a9.sh` | `781779523bbf4429b0fd8658055a99a8fb81b0b7cbf0de7285566a8edf87df64` |
| `tools/run-tp4-mtp0-current-vision-a9-client.sh` | `0e6cdb7302db7126afd24e972af63a41b128909fa8456de548f5162855b3953c` |
| `tools/supervise-tp4-mtp0-current-vision-a9.sh` | `3a665f1a4ec79372e4caaecff808053946a065b64a0b444bfbc7da8b3fff4eab` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |
| `data/20260828-tp4-mtp0-fixed-vision-attempt8-administrative-closeout.json` | `99285322635e6245ac85783671f6bc36a9a9dc126bdab8b490069c06b62a255d` |

Stop without retry on any gate failure and preserve partial evidence. Do not
add a family or measurement row until a separate closeout reviews a completed,
immutable result.
