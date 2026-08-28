# Flash-Next TP4 eager MTP0 fixed-vision attempt 5 preregistration

Date: 2026-08-28

Attempt 5 is a mechanically fresh retry after attempt 4 stopped before
admission at the unchanged 110-GiB MemAvailable floor. There is no runtime
treatment to the serving or performance path: the model, source, staged
runtime, TP4/EP4, eager MTP0, selective UVA, KV cache, modality, quality cases,
timeouts, health checks, resource floors, and teardown are identical to
attempt 4. The sole non-identity administrative treatment is upgrading the
shared process classifier and its receipt gates from schema v2 to v3.

The shared runtime scan is frozen at schema
`neural.download.q38-runtime-conflict-scan.v3`. It treats only a process that
vanishes between `/proc` enumeration and its initial `stat` read as a benign
race, records every such event explicitly, and continues to fail closed on
every other read error or identity inconsistency. A bound scanner, supervisor,
or parent must retain its saved PID/start-time/parent identity through the full
scan; disappearance or identity change remains a classifier error. All three
attempt-5 receipts also validate the positive integer PID, non-excluded status,
and exact benign-race record shape before admission or clean postflight can
pass.

These administrative identities also change:

- attempt 5 and state prefix `/tmp/q38-mtp0-current-vision-a5`;
- port `19683`;
- fresh attempt-5 run, supervisor-evidence, and cache paths;
- short compile/RPC roots `/tmp/q38v-a5-c` and `/tmp/q38v-a5-r`.

The UUID-derived RPC path remains exactly 51 bytes against the 107-byte limit.
The 110-GiB initial RAM floor is not lowered. The arm retains the same Grade-C
maximum and grants no result unless all existing gates pass.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a5.sh` | `15fa0b307d4996727dabca2dea13b312f703d30f3b6fde532804106c67c47d66` |
| `tools/run-tp4-mtp0-current-vision-a5-client.sh` | `80b1129b42d6c4674e7eb0eeb39374e95b89fd88354dd64659c0a20bbaea85a5` |
| `tools/supervise-tp4-mtp0-current-vision-a5.sh` | `e73a8d382f54c26da68b22bc5f9719da13f505cf753a9f142086a379c0de073d` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/test-q38-vision-ipc-path-policy.sh` | `a1f513431107cdee860b649c96bcd8295f2840b504bcde8fee260834008b2477` |

Stop without retry on any existing gate failure and preserve partial evidence.
Do not add a family or measurement row until a separate closeout reviews a
completed immutable result.
