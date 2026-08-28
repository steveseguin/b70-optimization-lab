# Flash-Next TP4 eager MTP0 fixed-vision attempt 6 preregistration

Date: 2026-08-28

Attempt 6 is a bounded retry after attempt 5 stopped before admission because
MemAvailable crossed below the 110-GiB initial floor between the drop-caches
precheck and the supervisor's own sample. Attempt 5 created no evidence,
lifecycle state, serving process, model load, request, or result.

The sole treatment is administrative: lower the one-time initial MemAvailable
admission floor by exactly 1 GiB, from 115,343,360 KiB (110 GiB) to
114,294,784 KiB (109 GiB). Clean-idle observations have been stable around
109.4--110.6 GiB, while prior successful eager loading retained about 29 GiB
MemAvailable. The active-run stop floors remain exactly 10 GiB MemAvailable and
5 GiB SwapFree. This treatment changes neither the serving/performance path nor
any performance claim.

Every model and serving identity remains frozen: current model revision and
staged runtime, TP4/EP4, eager MTP0, selective UVA placement, KV cache,
max-model-len 512, one-image/video-zero modality limit, zero processor cache,
encoder TP weights, same-boot text recovery, seven semantic cases, nine fixed
vision requests, health checks, timeouts, classifier v3 receipts, cleanup, and
the Grade-C maximum. No result is granted unless every existing gate passes.

Fresh administrative identities are:

- attempt 6 and state prefix `/tmp/q38-mtp0-current-vision-a6`;
- port `19685`;
- fresh attempt-6 run, supervisor-evidence, and cache paths;
- short compile/RPC roots `/tmp/q38v-a6-c` and `/tmp/q38v-a6-r`.

The UUID-derived RPC path remains exactly 51 bytes against the 107-byte limit.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a6.sh` | `a145fc550885efa7ec4dd3464658224f73d3cb8d9dbbb107646d0c2257e5691c` |
| `tools/run-tp4-mtp0-current-vision-a6-client.sh` | `90233b4fa74644eb1e5b3887841b3e3e850055f42fc3effd7723d727cd4ac036` |
| `tools/supervise-tp4-mtp0-current-vision-a6.sh` | `5a8be55ce6ecb78ecf699cf77d70692bd8d3f3bb485fd19514167ab746ee47aa` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |
| `data/20260828-tp4-mtp0-fixed-vision-attempt5-administrative-closeout.json` | `fb026d23211ea471c29557290e31a2508f0b184821e328939562bf564a538af6` |

Stop without retry on any gate failure and preserve partial evidence. Do not
add a family or measurement row until a separate closeout reviews a completed,
immutable result.
