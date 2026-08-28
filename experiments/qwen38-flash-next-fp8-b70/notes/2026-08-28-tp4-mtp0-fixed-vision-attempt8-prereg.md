# Flash-Next TP4 eager MTP0 fixed-vision attempt 8 preregistration

Date: 2026-08-28

Attempt 8 is a bounded retry after attempt 7 stopped at the frozen 900-second
user-manager stability gate, before memory admission, evidence creation, card
or collective health, launcher, or model work. The sole treatment is a fresh
administrative identity after waiting for that complete stability window.

There is no admission-threshold treatment. The one-time initial MemAvailable
floor remains exactly 113,246,208 KiB (108 GiB), the initial SwapFree floor
remains 6 GiB, and the active-run stop floors remain 10 GiB MemAvailable and
5 GiB SwapFree. Attempt 7's external pre-supervisor sample was only
111,501,980 KiB MemAvailable, below the still-frozen floor; attempt 8 must stop
again if its new sample remains below the gate. No further floor reduction is
preauthorized.

Every model and serving identity remains frozen: current model revision and
staged runtime, TP4/EP4, eager MTP0, selective UVA placement, KV cache,
max-model-len 512, one-image/video-zero modality limit, zero processor cache,
encoder TP weights, same-boot text recovery, seven semantic cases, nine fixed
vision requests, health checks, timeouts, classifier v3 receipts, cleanup, and
the Grade-C maximum. No result is granted unless every existing gate passes,
and this retry makes no performance claim.

Fresh administrative identities are:

- attempt 8 and state prefix `/tmp/q38-mtp0-current-vision-a8`;
- port `19687`;
- fresh attempt-8 run, supervisor-evidence, and cache paths;
- short compile/RPC roots `/tmp/q38v-a8-c` and `/tmp/q38v-a8-r`.

The UUID-derived RPC path remains exactly 51 bytes against the 107-byte limit.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a8.sh` | `3c3430c3ec1f72dfac2cc1cf8f52b1f4ee1afe4ecef422665e33381ae5c29d19` |
| `tools/run-tp4-mtp0-current-vision-a8-client.sh` | `9b052fe1af623d2e8c70b931e3567ef0d8a189fc655234aa5216ee6c243e90a2` |
| `tools/supervise-tp4-mtp0-current-vision-a8.sh` | `b7c183595fbb6637d66fe765a205322caaac2411f78b5287092010f1e341e6c3` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |
| `data/20260828-tp4-mtp0-fixed-vision-attempt7-administrative-closeout.json` | `f1e342e2002142ccfe6a7a3c264e20276e90a2d51cd54bb50edbe6f45dd2759b` |

Stop without retry on any gate failure and preserve partial evidence. Do not
add a family or measurement row until a separate closeout reviews a completed,
immutable result.
