# Packet 118 launch procedure (for the coordinator; the authoring agent never launches)

**118 = 117 + three server-side levers, each launch-selectable, exact by construction, with an off form that is
117's code path:** the timing split (always on, measurement only), the four-card safety snapshot from residence
fingerprints (`LTX_SNAPSHOT_MODE=walk|fingerprint`, default `fingerprint`), and the decoder-graph pool cap
(`LTX_DECODER_GRAPH_POOL_CAP_GB`, default unset = 117). No request graph and no output byte changes; the 117
levers (cone, overlap, prep-ahead, 121 frames) are unchanged. Design: `notes/2026-10-09-continuation118-stream-design.md`.

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118` |
| Manifest SHA-256 | `cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6` |
| Payload | 121,138,538 bytes (`du -sb`; 117 was 118,824,767) |
| Parent | packet 117, manifest `5826174e…0802c9` (verified at load and at launch, with 116b … 111 behind it) |
| Plan | `4bd3a1dc915617a8e40e249014b748a46196e8229d24d5c5ac844fae54cc697f`; 132 qualification ids (same keys as 117, new identities), 264 graph pins per qualification row |
| Build receipt | `data/resume-20261008/continuation118-build.json` |
| Unit | `ltx118-stream-server-20261009` |
| Launch script | `recovery/20261009-continuation118-stream/launch-118.sh <frames> <anchor> <dg> <ad> <bo> <pa> <walk\|fingerprint> <cap GB\|-> <receipt> [--check-only]` |
| Client | `stream/start-client-118.sh <frames> <dg> <ad> <bo> <pa> <walk\|fingerprint> <cap GB\|none>` (`ltx_continuation_client.py --packet 118 … --expect-snapshot-mode … --expect-pool-cap-gb …`) |

## 0. What is different from 117, operationally

- **`LTX_SNAPSHOT_MODE=walk|fingerprint`** (set explicitly). `fingerprint`: each four-card snapshot runs 117's
  checks with the residence/ownership and the sampler placement from fact tuples bound, at the placement event, to
  the admitted fingerprints; whenever a fact differs the walk itself decides. Setup and qualification run every
  snapshot in both modes and compare (the walk's snapshot is admitted); streaming runs the walk beside the
  fingerprint on every 20th chunk and from any near-floor reading (within 0.5 GiB of a pre-request floor) on, for
  that chunk. A disagreement latches the server and writes
  `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/snapshot-118-refused.json`; the launcher then refuses
  `fingerprint` (walk still admitted). `walk` = 117's inspection, timed.
- **`LTX_DECODER_GRAPH_POOL_CAP_GB=<GB>`** (optional, decimal GB 0.25–16, two decimals at most, needs
  `LTX_DECODER_GRAPH=1`). Unset = 117. Set: `forward_pre_diffusion` is captured first; `forward_diff_step` is
  captured only if the measured reserved growth of the first capture is below the cap, otherwise it runs eagerly
  with the same caches for the life of the server. Recommended: unset at 97 frames; `1.0` for a 121-frame dg1
  launch (keeps `forward_diff_step` eager, frees ≈ 1.9 GB on xpu:3, estimate).
- **Timing split**: receipts carry `timing_s.submit_split`, `snapshots`, `node_starts_ns`, `authority_checks`,
  `turnaround`, `server_options` (CONTRACT.md §"What changed from packet 117").
- **Latches checked by the launcher (also `--check-only`)**: `decoder-graph-116-refused.json` refuses
  `LTX_DECODER_GRAPH=1`; `anchor-decode-118-refused.json` or `anchor-decode-117-refused.json` refuses
  `LTX_ANCHOR_DECODE=cone`; `precompute-118-refused.json` or `precompute-117-refused.json` refuses
  `LTX_BENCODE_OVERLAP=1` / `LTX_PREP_AHEAD=1`; `snapshot-118-refused.json` refuses `LTX_SNAPSHOT_MODE=fingerprint`.
  None exists at the build (the 117 121-frame precompute latch was archived on 2026-10-09).
- **Names:** `stream118-…`; the launcher refuses any 118 setup/qualification name or `stream118-` entry under
  `output/`, `output/validation/`, `requests/` (also `--check-only`). The 117 runs' `stream117-` names do not collide.
- Same model files and native code as 117 (sampler, decoder source, upsampler, text encoder, `nodes_lt.py`,
  `conditioning_guard.py`, `candidate_safety.py`, `native_bindings.py`, `latent_anchor.py`, `stream_decode.py`,
  `stream_preview.py`: byte-for-byte). Same floors.

## 1. Fresh admission (immediately before launch)

1. **No other stream server running**: the live `ltx117-stream-server-20261008` (and its client
   `ltx117-stream-client-20261008`) are stopped by one controlled application stop each (client first; an
   application stop, not a host restart). Nothing may own port 8188 (the Flash-Next lane may be using the cards:
   wait for its controlled stop, never touch it). **Five-minute gap** between that stop and this launch. No retry,
   no restart loop.
2. **`FAULT.json` absent** at the results root; the latch files of §0 absent for the levers you set.
3. **Health receipt:** four-card postflight probe, same boot, under 6 hours old. Do not poll xpu-smi while a
   server initialises.
4. **Storage** (the launcher repeats it):

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-118-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   At build time: 111,271,104,512 bytes available against 53,854,863,360 required (50 GiB reserve + 160 MiB build), 111,103,332,352 remaining after the build allowance.
5. **Names:** `ls output output/validation requests | grep stream118` (in the results root) must print nothing.
6. **No `__pycache__`** in the packet (0 after the build). Use `-B`.
7. **Rehearsal (`--check-only`)**, venv Python, soft `NOFILE` >= 65536, not through systemd-run, with the fresh
   receipt. **Not run by the authoring agent** (it needs the fresh health receipt and runs only through the
   coordinator):

   ```
   recovery/20261009-continuation118-stream/launch-118.sh 97 frame 1 cone 1 1 fingerprint - <fresh health receipt> --check-only
   ```

   which is exactly:

   ```
   cd /home/steve/llm-optimizations && ulimit -Sn 65536 && env EnableDeferBacking=0 LTX_ANCHOR=frame LTX_DECODER_GRAPH=1 \
     LTX_ANCHOR_DECODE=cone LTX_BENCODE_OVERLAP=1 LTX_PREP_AHEAD=1 LTX_SNAPSHOT_MODE=fingerprint LTX_BUSY_WINDOWS=0 \
     LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 \
     LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=97 \
     LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
     /home/steve/.venvs/ltx25-baseline/bin/python -B \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118/launch/serve-encoder.py \
     --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118 \
     --manifest-sha256 cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6 \
     --run-name encoder-server-continuation-stream-118-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
     --health-receipt <fresh four-card health receipt> --check-only
   ```

   Pass = every environment/lever/latch rule, the run-name and run-dir checks, the full packet verification (118 →
   117 → … 111), the naming preflight, the dependency activation, the runtime and model-receipt verification and
   the storage admission, then it returns before any lock or device work.

## 2. Launch command (recommended first launch: 97 frames, frame anchor, every lever on, fingerprint)

```
recovery/20261009-continuation118-stream/launch-118.sh 97 frame 1 cone 1 1 fingerprint - <fresh health receipt>
```

which runs:

```
systemd-run --user --unit=ltx118-stream-server-20261009 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_ANCHOR=frame LTX_DECODER_GRAPH=1 LTX_ANCHOR_DECODE=cone LTX_BENCODE_OVERLAP=1 \
  LTX_PREP_AHEAD=1 LTX_SNAPSHOT_MODE=fingerprint LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 \
  LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 \
  LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=97 LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118 \
  --manifest-sha256 cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6 \
  --run-name encoder-server-continuation-stream-118-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97 \
  --health-receipt <fresh four-card health receipt>
```

then the client: `stream/start-client-118.sh 97 1 cone 1 1 fingerprint none`.

Run names: `encoder-server-continuation-stream-118-<anchor>-dg<0|1>-ad<full|cone>-bo<0|1>-pa<0|1>-sm<walk|fp>-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames>`,
matching `LTX_ANCHOR`, `LTX_DECODER_GRAPH`, `LTX_ANCHOR_DECODE`, `LTX_BENCODE_OVERLAP`, `LTX_PREP_AHEAD`,
`LTX_SNAPSHOT_MODE`, `LTX_SAMPLER_PLACEMENT`, `LTX_STREAM_FRAMES` (the launcher refuses any mismatch; 264 names: the
132 variants of 117 × two snapshot modes). The pool cap is not in the name (it is in the status, every receipt
and every decode record). The launches that matter, on two-way20-28, frame anchor, cone/1/1:

| order | frames | dg | sm | cap | run name | why |
|---|---|---|---|---|---|---|
| 1 | 97 | 1 | fp | – | `…-118-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-…-f97` | target: fingerprint snapshots + the timing split |
| 2 | 121 | 1 | fp | 1.0 | `…-118-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-…-f121` | 121 frames with the decoder graph inside the xpu:3 floor |
| 3 | 97 | 1 | walk | – | `…-118-frame-dg1-adcone-bo1-pa1-smwalk-two-way20-28-…-f97` | control: 117's snapshots on 118 code (same bytes), only if the dual parts are ambiguous |
| (if 2 is refused) | 121 | 0 | fp | – | `…-118-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-…-f121` | 117's 121 dg0 lane with fingerprint snapshots |

## 3. Health and identity after start

`GET /ltx-stream/status`: `phase: "stream_setup"`, `halted: null`, `fault: false`, `packet: 118`,
`anchor: "frame"`, `decoder_graph: 1`, `anchor_decode: "cone"`, `bencode_overlap: 1`, `prep_ahead: 1`,
`snapshot_mode: "fingerprint"`, `decoder_graph_pool_cap_bytes: null` (or `1000000000` with cap 1.0),
`features.timing_split: true`, `features.snapshot_fingerprint: true`, `features.decoder_graph_pool_cap` (cap set),
the 117 features, `runtime_manifest_sha256` as above. After `stream118-prepare`: `stream-preparation.json` has
`snapshot_mode` and `residence_ledger` (`ready: true`, seven bound fingerprints equal to the admitted ones, tensor
counts per role, the constructor exception `model_sampling.sigmas`); `stream-decoder-graph-install.json` and
`stream-anchor-decode-install.json` as 117. `snapshot_state.ledger.stats` counts fingerprint snapshots, fallback
walks (0 expected), dual walks, agreements (= dual walks) and disagreements (0).

## 4. Memory (estimates from the 117 receipts; the floors are the stop rule)

| card | 97, dg1, fp | 121, dg1, cap 1.0, fp | 121, dg0, fp | floor |
|---|---|---|---|---|
| xpu:0 | 10.37 GB before stage B on 117 (1.78 GB above 8.59 GB); 118 adds nothing on any card (the ledger is ≈ 7k host tuples) | ≈ 10.25 GB (117 at 121) | 10.25 GB (117) | 8 GiB |
| xpu:1 | 10.72 GB | ≈ 10.62 GB | 10.62 GB | 8 GiB |
| xpu:2 | ≈ 12.6 GB | ≈ 12.5 GB | ≈ 12.5 GB | 2 GiB |
| xpu:3 | 12.09 GB before every decode on 117 (2.4 GB above 9.66) | 117 dg1 without a cap: 9.59 GB at graph chunk 1 (76 MB short). With the cap the `forward_diff_step` capture (pool + side-stream warm-up, ≈ 1.51 GB at 97 ×1.25) is not made: **≈ 11.0–11.8 GB** at the precompute snapshots (1.3–2.1 GB above 9.66; < 10.16 falsifies) | 15.64 GB (117) | 9 GiB (9.66 GB) before every decode, every conditioning stage and every precomputed encode; 2 GiB after |

Actual numbers: receipts `memory.*`, `snapshots[].min_margin_bytes` (smallest card margin above its pre-request floor
at each snapshot), decode records `xpu3_free_before_decode`, `decoder.pool {cap_bytes, growth_bytes, captured,
capped}`, `precompute.{A,B}.record.before/after.physical_free_bytes`, `stream-freeze.json` → `decoder_graph`.
Storage: 9 captures of 78 MB (97) / 97.6 MB (121) inside the 3 GiB run allowance.

## 5. Qualification (11 requests and one verdict action)

Client (default) or `resolution/components/qualify_client.py --frames 97 --anchor frame --decoder-graph 1
--anchor-decode cone --bencode-overlap 1 --prep-ahead 1 --placement two-way20-28 --text-reuse 1
--snapshot-mode fingerprint [--pool-cap-gb 1.0]`. Order: window probe, prepare, eager chain (3), graph chain (3),
repeat chain (3, stream form), verdict.

**Pass looks like** (`stream-qualification-verdict.json`): everything 117 §5 lists (exact replay, lever rows,
decoder rows, the 49/97 reference check), plus:

- `server_options` = the launch's; `snapshot_failures: []`;
- `snapshot_rows`: nine rows; labels `request-before, request-after` on chunk 0 of each chain and `request-before,
  A-before, A-after, B-before, B-after, request-after` on chunks 1–2; all `mode: fingerprint`, all `dual: true`,
  all `agree: true` (walk mode: all `dual: false`);
- with cap 1.0: `decoder_graph_rows[qgraph-c000000].pool = {cap_bytes: 1000000000, captured:
  [forward_pre_diffusion], capped: [forward_diff_step]}`, `new_captures` `0,0,0,1,0,0,0,0,0`; without a cap as 117
  (`0,0,0,2,0,…`).

Any failure halts streaming; no retry. A snapshot disagreement also writes `snapshot-118-refused.json`.

## 6. Streaming: what to watch and the predictions

Per chunk (receipt): `timing_s.submit_split` (the named sub-buckets; `other` must stay < 0.05 s, else a step is
unmarked), `snapshots[].{seconds, parts_s, dual, min_margin_bytes}` (on every 20th chunk `parts_s.dual_walk` and
`parts_s.dual_fingerprint` time the two modes on the same snapshot), `authority_checks.{healthy_calls, healthy_s,
plan_digest_s, status_route_calls, status_route_s}`, `turnaround.split.{receipt_staged_to_commit, commit_write,
commit_to_first_served, served_to_admission, admission_parse, other}`; the client's manifest line adds
`client_turnaround_s` and `client_post_s`. Status: `snapshot_state.ledger.stats.{fallback_walks: 0,
disagreements: 0}`.

Predictions (medians of 100 stream chunks after the first 10; 117 measured 4.82 s at 97 dg1 and 5.40 s at 121
dg0):

| launch | period | work / s video | falsified if |
|---|---|---|---|
| 97, dg1, fp | **4.65–4.78 s** (central 4.72) | 1.15–1.18 | > 4.82 or < 4.55 |
| 121, dg1, cap 1.0, fp | **5.15–5.32 s** (central 5.25) | 1.02–1.06 | > 5.37, or xpu:3 < 10.16 GB at any snapshot |
| 121, dg0, fp | 5.25–5.37 s (central 5.31) | 1.04–1.07 | > 5.40 |
| 97, dg1, walk (control) | 4.74–4.90 s (= 117) | 1.17–1.21 | outside 4.70–4.95 |

- Snapshot cost: `snapshots[].seconds` walk 0.04–0.10 s, fingerprint 0.03–0.07 s; `dual_fingerprint / dual_walk`
  0.5–0.8 (falsified above 0.9). Per chunk −0.06 to −0.20 s (central −0.10).
- Timing split at 97 (estimates; what the split is for): request-before + stage-A snapshots 0.12–0.25 s,
  `precheck` + `authority_begin` 0.04–0.12 s, `authority_checks.plan_digest_s` 0.1–0.2 s per chunk (4.3 ms per
  `healthy()` on this CPU), turnaround `commit_to_first_served` 0.02–0.08 s, `served_to_admission` 0.02–0.10 s.
- 121 cap 1.0: the cone on the chain 0.80–0.92 s (stages 1–4 replayed; 117 dg0 0.955), display decode (off-chain,
  stage 5 eager) 2.4–2.7 s, `cone_equal` true on every chunk.

Seams as 117 (same bytes by the gates). Stop rules as 117 plus: a snapshot disagreement latches. A GPU fault halts
new requests; one controlled stop (`systemctl --user stop ltx118-stream-server-20261009`, one SIGINT) is the single
incident action. No restart loop, no reboot, no settings change.

## 7. Owner view

Nothing new to look at: 118 changes no output byte (the gates prove it per launch), so the frames at 97 and 121 are
117's for the same seeds (a 121-frame dg1-capped launch decodes to the bytes 117's 121 dg0 run delivered, by the
decoder graph's byte gate). The owner seam view (`recovery/20261008-continuation115-stream/owner_seam_view.py`)
over twenty chunks of `data/stream/kittens-01.json` is optional; the owner-visible change is the safety
inspection itself: decide whether fingerprint snapshots (dual-checked in qualification and every 20th chunk) are
acceptable as the default, and whether the plan-identity check (`authority_checks.plan_digest_s`) should become a
frozen plan (not in 118).
