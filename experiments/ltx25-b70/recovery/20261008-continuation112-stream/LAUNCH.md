# Packet 112 launch procedure (for the coordinator; the authoring agent never launches)

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112` |
| Manifest SHA-256 | `e49f669d580a55d7f2a99ddfc5c2c5fc4a22dd7168987eb471704e2be6352b91` |
| Payload | 111,971,892 bytes |
| Build receipt | `data/resume-20261008/continuation112-build.json` |

## 0. Decide before launch: placement against the xpu:0 floor

The brief keeps the preregistered admission floors: 8/8/2/9 GiB free before each
request and before each conditioning stage, and 2 GiB after. The brief also asks
for the 256² lane's placement, `two-way` (blocks 0–22 on xpu:0, 23–47 on xpu:1).
Measured history says these two requirements collide on xpu:0:

- **Packet 96/97 at the freeze** (256², two-way, two graph pools): xpu:0 had
  7.534 GiB free. Each pool cost 0.266 GiB, so the eager free figure is about
  **8.07 GiB**.
  Sources: `data/batch-96/two-way-w2-b1-p1/sampler-capture-freeze-*.json`,
  `data/place-97/two-way-w2-b1-p1-dxpu2/…freeze.json`.
- **Packet 111** (20/28, eager): xpu:0 dropped by 0.62 GiB after its first chunk
  because the allocator retains memory. At 256² the retention is smaller, but
  it is not zero.
- **Prediction for 112 with `two-way`:** about 7.7–7.9 GiB free on xpu:0 before
  the second eager chunk, and about 7.2–7.6 GiB once the graph pool exists. That
  is **below the unchanged 8 GiB floor**. The server would refuse cleanly, with a
  latch, an evidence file and no retry, early in qualification.

Placement is therefore a launch parameter, so you can choose without a rebuild:

| `LTX_SAMPLER_PLACEMENT` | expected free xpu:0 / xpu:1 / xpu:2 / xpu:3 before a chunk (GiB) | vs floors 8/8/2/9 |
|---|---|---|
| `two-way` (brief default) | ~7.2–8.1 / ~12.3–12.8 / ~11.8 / ~14.5 | **xpu:0 fails or is marginal** |
| `two-way20-28` (the 111 placement) | ~10.0–11.0 / ~10.2–10.6 / ~11.8 / ~14.5 | passes with ~2 GiB margin |

The 20/28 xpu:0/xpu:1 column comes from packet 111's measured
10.28–10.97 / 10.54–10.57 GiB at 640×384×49 eager, minus a ~0.3–0.6 GiB
graph-pool allowance. Activations at 256² are smaller, so the real readings
should be equal or higher.

Neither placement changes arithmetic, and the qualification gate compares
chains within one launch. If `two-way` is required, the owner must approve a
256²-specific xpu:0 pre-floor. That change goes in `native_safety.PRE_BYTES`
semantics and needs a rebuild. This packet does not lower it.

## 1. Fresh admission (immediately before launch)

1. A four-card health probe receipt from the same boot, less than 6 hours old,
   from the existing `scripts/check-four-card-health.py` procedure, exactly as
   for 111. The launcher refuses without one.
2. Storage:

   ```
   python3 /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-112-<placement>-w1-b1-p1-dxpu2-s256x256-f<frames> \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   It must report `admitted: true`. At build time 58,080,661,504 bytes
   (54.09 GiB) were free, against 53.0 GiB needed. The launcher repeats this
   check itself.
3. The previous application must be stopped by the controlled single-reload
   procedure: one SIGINT, then postflight. Nothing may own port 8188, the GPU
   locks or the render nodes. The launcher checks and refuses otherwise. A live
   stream server currently owns the cards, so this is a planned reload that you
   decide on. It is not part of this packet.
4. No `__pycache__` is in the packet (verified 0 after build and after the CPU
   `--check-only` runs).

## 2. Launch command (mirrors `continuation111-launch-command.json`)

Defaults: 49 frames, text reuse off. `<PL>` is `two-way20-28` or `two-way`
(see §0).

```
systemd-run --user --unit=ltx112-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 \
  LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=<PL> LTX_SAMPLER_SHARED_POOL=1 \
  LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=49 LTX_STREAM_TEXT_REUSE=0 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112 \
  --manifest-sha256 e49f669d580a55d7f2a99ddfc5c2c5fc4a22dd7168987eb471704e2be6352b91 \
  --run-name encoder-server-continuation-stream-112-<PL>-w1-b1-p1-dxpu2-s256x256-f49 \
  --health-receipt <fresh four-card health receipt>
```

Environment variables:

- **All of them are required, and the launcher refuses any deviation.**
- `LTX_STREAM_FRAMES`: `49` (default, 2.04 s per chunk) or `25`. The run name
  suffix must match (`-f49` or `-f25`).
- `LTX_SAMPLER_PLACEMENT`: `two-way` or `two-way20-28`. It must match the run
  name.
- `LTX_STREAM_TEXT_REUSE`: `0` (default, re-encode every chunk) or `1`. The
  owner decides; see the design note.
- `LTX_SAMPLER_WORKERS=1`: a single sampler worker.
- `LTX_DECODE_REPLICAS=1` and `LTX_DECODE_REPLICA_DEVICE=xpu:2`: the 97
  configuration. The streaming graph decodes with the native VAE on xpu:3 and
  builds no replica (§6).

Optional rehearsal, the same as for 111: the same command line with
`--check-only`, run directly with the venv Python rather than through
`systemd-run`. It does no device or port work. It passed for 49/two-way,
25/two-way and 49/two-way20-28 on 2026-10-08 using postflight-111 as the health
receipt.

## 3. Health and identity after start

Wait for `GET http://127.0.0.1:8188/ltx-stream/status` to return 200 with:

- `phase: "stream_setup"`, `halted: null`, `fault: false`
- `frames` and `placement` equal to the launch environment
- `runtime_manifest_sha256` equal to the manifest above

Check the run directory for `server-identity.json`, `stream-executor-guard.json`,
`health-receipt.json` and `journal-admitted-faults.txt`. Do not send anything
else to the server before the qualification driver.

## 4. Qualification (runs first; 11 requests plus one verdict action)

```
/home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112/resolution/components/qualify_client.py \
  --frames 49 --placement <PL> --text-reuse 0 \
  --log /home/steve/llm-optimizations/experiments/ltx25-b70/data/resume-20261008/continuation112-qualify.jsonl
```

`--dry-run` prints the graph hashes without network access.

The requests run in this order. The driver submits each one after the previous
one completes, makes one attempt each, and has bounded waits: 1800 s for setup,
900 s per chunk.

1. `stream112-window-probe`: the 110/111 text-window probe, which captures the
   text graphs (~330 s on 111).
2. `stream112-prepare`: full residency, plus admission of the candidate safety
   controller.
3. `stream112-qeager-c000000` … `c000002`: the eager chain. The gate runs in
   `original` mode, so the sampler has no routes. Each request writes a full
   capture.
4. `stream112-qgraph-c000000` … `c000002`: the graph-replay chain. The gate in
   `graph` mode installs all 48 routes with chain 1. c000 captures the unmasked
   signatures, c001 the masked ones, and c002 must capture nothing.
5. `stream112-qrepeat-c000000` … `c000002`: the exact repeat, using the
   streaming graph form (no gate nodes). It must capture nothing.
6. `POST /ltx-stream/action {"action":"qualify-verdict"}`.

Every chain uses its own predecessor's last frame. Chunk 1 repeats chunk 0's
prompt. Chunk 2 is a cut: a new prompt on the same anchor chain.

Full captures are written only for these nine requests:

- 49 frames: 9 × 39,628,040 bytes = 356,652,360 bytes
- 25 frames: 9 × 20,258,568 bytes = 182,327,112 bytes

The prewrite guard bounds this exactly.

**Pass** means the verdict returns `{"passed": true, "phase": "stream", "qualified_text_windows": [64]}`
and `stream-qualification-verdict.json` shows:

- `exact_replay`: for each chunk, all four tensors identical across the three
  chains, with `all_four_identical: true`.
- Capture-file re-reads equal the output-node hashes.
- Every anchor equals the last frame of its capture.
- The eager chain has 0 routes. qgraph c002 and all of qrepeat have
  `new_captures` 0.
- `signatures_per_route` is at most 8 and uniform across routes. The expected
  value is 4 (stage A and B, unmasked and masked), but this is unverified.
- `failures: []`.

After that, `stream-freeze.json` records the frozen per-route signature digests,
and `CAPTURES_FROZEN` is set.

**Fail** means any mismatch, refusal, fault, nonfinite value or floor miss. The
server latches (`stream-halt.json`) and refuses all streaming with 503. Keep the
process for inspection and do not retry. Per-request evidence is in the run
directory: `stream-before-*`, `stream-after-*`, `safety-*`, `receipts/` and
`stream-failure-*`.

## 5. Expected memory per card

The full residency is unchanged from 111: sampler xpu:0/1, upsampler xpu:0,
text encoder 24/24 on xpu:2/3, both VAEs on xpu:3. The figures below are
estimates, not measurements, and the admission checks are authoritative.

- **Sampler (xpu:0, xpu:1).** At 256²×49 there are 7×8×8 = 448 stage-B tokens.
  That compares with 256 at 256²×25 and 1,680 at 640×384×49. Transient
  activations are about 1.75× the 256²×25 lane and about 0.27× of 111.
- **Graph pool (W1, shared).** At 256²×25 with B1 and 2 signatures, the pool
  cost 0.27 GiB on xpu:0 and 0.23 GiB on xpu:1. With 4 signatures and 49 frames,
  allow about 0.5–0.9 GiB on xpu:0 and 0.4–0.8 GiB on xpu:1. That figure is
  extrapolated; the qualification receipts measure it.
- **Decoder (xpu:3).** 49 frames at 256² is about 0.27× the pixel volume of 111.
  111 kept xpu:3 at ≥14.50 GiB free before and after every chunk, with a
  17.1 GiB allocated peak. Expect xpu:3 at ≥14 GiB free, against a 9 GiB floor.
- **Conditioning encodes.** The source estimate is 80·7·H·W·2 bytes: 18.4 MB at
  stage A (128²) and 73.4 MB at stage B (256²). This is negligible next to the
  floors.
- **xpu:2.** Text primary only, about 11.8 GiB free, against a 2 GiB floor.
- The binding constraint is xpu:0, as described in §0.

## 6. What is intentionally not enabled

- **Decoder replica decode on xpu:2.** The 97 replica path is
  `LTXPipelineDecode` run-behind. It requires `LTXPipelineSampler` sentries and
  emits a clip `depth` prompts late, which conflicts with serial anchoring,
  where the next chunk needs this chunk's decoded frame now. The environment is
  kept as in 97 and 111, but the replica count must stay at 0. See the open
  questions in the design note.
- **Lean connector memo.** It stays off. The note recommends it as a later,
  separate lever.

## 7. Streaming

After the verdict passes, the stream client follows `CONTRACT.md`. The
per-chunk lag is in each receipt as `timing_s.submit_to_preview_written`.

Storage: the stream may use 3 GiB net of new writes, beyond the captures.
Expected cost per chunk is about 0.8 MB anchor (only the two newest are kept),
an unmeasured preview MP4 of about 0.1–0.5 MB, about 10 KB of receipt and about
14 KB of text-node receipt. That gives several thousand chunks before the
allowance latches, which is roughly 3 hours or more at 49 frames. Deleting
consumed previews extends this.

To stop the server: one SIGINT (`systemctl --user stop ltx112-stream-server-20261008`)
followed by the usual postflight. Never use a restart loop.
