# Flash-Next TP4 eager MTP0 fixed-vision attempt 7 preregistration

Date: 2026-08-28

Attempt 7 is a bounded retry after attempt 6 stopped before its supervisor was
invoked. The exact post-`sync`/drop-caches sample was 113,701,160 KiB
MemAvailable, 593,624 KiB below the frozen 109-GiB gate; SwapFree was
6,296,432 KiB. Attempt 6 therefore created no evidence, lifecycle state,
serving process, model load, request, or result.

The sole treatment is administrative: lower the one-time initial MemAvailable
admission floor by exactly 1 GiB, from 114,294,784 KiB (109 GiB) to
113,246,208 KiB (108 GiB). The observed attempt-6 sample would clear the new
floor by 454,952 KiB. The active-run stop floors remain exactly 10 GiB
MemAvailable and 5 GiB SwapFree; the separate initial 6-GiB SwapFree admission
gate also remains unchanged. This treatment changes neither the
serving/performance path nor any performance claim.

Every model and serving identity remains frozen: current model revision and
staged runtime, TP4/EP4, eager MTP0, selective UVA placement, KV cache,
max-model-len 512, one-image/video-zero modality limit, zero processor cache,
encoder TP weights, same-boot text recovery, seven semantic cases, nine fixed
vision requests, health checks, timeouts, classifier v3 receipts, cleanup, and
the Grade-C maximum. No result is granted unless every existing gate passes.

Fresh administrative identities are:

- attempt 7 and state prefix `/tmp/q38-mtp0-current-vision-a7`;
- port `19686`;
- fresh attempt-7 run, supervisor-evidence, and cache paths;
- short compile/RPC roots `/tmp/q38v-a7-c` and `/tmp/q38v-a7-r`.

The UUID-derived RPC path remains exactly 51 bytes against the 107-byte limit.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a7.sh` | `63123d37026b74d8a9c2f16a1b3d9400cf0a1bc05dbbd634f076e29a3b91679a` |
| `tools/run-tp4-mtp0-current-vision-a7-client.sh` | `bb698a717c3cea65302b100510cdd2a8aa08aedd14617a56d1fe7bc8eafaa1c7` |
| `tools/supervise-tp4-mtp0-current-vision-a7.sh` | `292c9dc8ff7f390ba6c5d649d48bd05e19e0c70dbf3af61b0797c04c1bcd7a31` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |
| `data/20260828-tp4-mtp0-fixed-vision-attempt6-administrative-closeout.json` | `3e0940eb7ed612ce3a04d3db26dcaaa1bc3f51708fe76ca493712ab44790b3e6` |

Stop without retry on any gate failure and preserve partial evidence. Do not
add a family or measurement row until a separate closeout reviews a completed,
immutable result.
