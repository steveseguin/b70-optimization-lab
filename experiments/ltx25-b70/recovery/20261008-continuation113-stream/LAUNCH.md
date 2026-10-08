# Packet 113 launch procedure (for the coordinator; the authoring agent never launches)

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113` |
| Manifest SHA-256 | `a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b` |
| Payload | 112,614,223 bytes (`du -sb`; 112 was 111,971,892) |
| Parent | packet 112, manifest `e49f669d…52b91` (verified at load and at launch, and 111 behind it) |
| Build receipt | `data/resume-20261008/continuation113-build.json` |
| Plan | `9dd583d4…a27317`. The qualification graphs and qualification ids are identical to 112's |

## 0. What is different from 112, operationally

- **Same model work.** Sampler, conditioning, text encoder, upsampler and decoder
  are byte-for-byte 112's files. The same placement options, floors (8/8/2/9 GiB
  before each chunk and each conditioning stage, 2 GiB after), latches and
  nine-chunk exact qualification apply.
- **Preview off the chain (lever 1).** The receipt is committed when the anchor is
  ready. The MP4 is written afterwards by one writer thread, and then
  `receipts/preview-<run_name>.json` appears. The client must run with
  `--packet 113`.
- **Chain reset.** A client may send `reset: 1`; see CONTRACT.md §1.
- **Anchor border diagnostic** in every receipt (`anchor_diagnostics`).
- **Lever 2 (graph-captured VAE decode) is not in this packet.** See the design
  note. **No new graph signature and no new graph pool exist on any card.** xpu:3
  memory is therefore 112's: on the live 112 lane, before a chunk, xpu:3 had
  14.74 GiB free (15,827,365,888 bytes), and 13.08 GiB after the decode peak.
  The floor there is 9 GiB.
- **Host RAM:** the writer holds at most 3 private CPU copies of a chunk's images
  and waveform (~39 MB each at 49 frames), so ≤ ~120 MB.

## 1. Fresh admission (immediately before launch)

1. **Stop 112 by the controlled single reload.** This is an application reload,
   not a host restart:

   ```
   systemctl --user stop ltx112-stream-server-20261008     # one SIGINT (KillSignal=SIGINT, no SIGKILL)
   ```

   Wait for the unit to be inactive. Stop the 112 stream client first, or let it
   exit on the halted/connection state; do not leave it polling. Nothing may own
   port 8188, the GPU locks or the render nodes. The launcher checks this and
   refuses otherwise. No retry, and no restart loop.
2. **Health receipt.** Run the four-card postflight health probe with the existing
   `scripts/check-four-card-health.py` procedure, as after 111 and 112. The
   receipt must be from the same boot and less than 6 hours old. Do not poll
   xpu-smi while a server is initialising.
3. **Storage**, which the launcher also repeats itself:

   ```
   python3 -B /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/launch/check-storage-headroom.py \
     /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-continuation-stream-113-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49 \
     --min-free-bytes 50GiB --planned-write-bytes 3GiB
   ```

   It must report `admitted: true`. On 2026-10-08 at build time: 58,184,531,968
   bytes available against 56,908,316,672 required (54.19 GiB vs 53.0 GiB), so
   54,963,306,496 bytes would remain after the 3 GiB allowance. **The margin is
   1.19 GiB.** The live 112 stream is still writing, so re-run the check after
   stopping 112. If it fails, delete consumed 112 previews first. The CONTRACT
   allows that; nothing else under the 112 run directory may be deleted.
4. **No `__pycache__`** in the packet: 0 after the build and after the
   `--check-only` runs. Every Python command here uses `-B`.
5. **Optional rehearsal:** the launch command below with `--check-only`, run
   directly with the venv Python and not through systemd-run. It does no device,
   lock or port work. It passed on 2026-10-08 for 49/two-way20-28, 49/two-way and
   25/two-way, using `data/resume-20261008/postflight-stream01.json`
   (`data/resume-20261008/continuation113-startup-check.json`).

## 2. Launch command

Run name `encoder-server-continuation-stream-113-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49`.
That is the live 112 lane's placement and frame count, and text reuse is off as in 112.

```
systemd-run --user --unit=ltx113-stream-server-20261008 \
  --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT \
  EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 \
  LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 \
  LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=49 LTX_STREAM_TEXT_REUSE=0 NEOReadDebugKeys=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113 \
  --manifest-sha256 a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b \
  --run-name encoder-server-continuation-stream-113-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49 \
  --health-receipt <fresh four-card health receipt>
```

The environment is exactly 112's, and the launcher refuses any deviation.
`LTX_STREAM_TEXT_REUSE` keeps 112's meaning and qualification path. The owner has
not ruled on reuse, so it stays `0`. `LTX_STREAM_FRAMES=25` and
`LTX_SAMPLER_PLACEMENT=two-way` remain valid launch options; the run name must
match.

## 3. Health and identity after start

Wait for `GET http://127.0.0.1:8188/ltx-stream/status` to return 200 with:

- `phase: "stream_setup"`, `halted: null`, `fault: false`
- `packet: 113`, `features` all true, and `preview_writer.failed: null`
- `frames: 49`, `placement: "two-way20-28"`, and `runtime_manifest_sha256` equal
  to the manifest above

Check the run directory for `server-identity.json`, `stream-executor-guard.json`,
`health-receipt.json` and `journal-admitted-faults.txt`.

## 4. Qualification (unchanged from 112: 11 requests and one verdict action)

Either the stream client runs it (it runs qualification by default):

```
/home/steve/.venvs/ltx25-baseline/bin/python -B /home/steve/llm-optimizations/experiments/ltx25-b70/stream/ltx_continuation_client.py \
  --packet 113 --work-dir <client work dir> [the 112 lane's usual client options]
```

or the packet's driver does:

```
/home/steve/.venvs/ltx25-baseline/bin/python -B \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-113/resolution/components/qualify_client.py \
  --frames 49 --placement two-way20-28 --text-reuse 0 \
  --log /home/steve/llm-optimizations/experiments/ltx25-b70/data/resume-20261008/continuation113-qualify.jsonl
```

The requests, captures (9 × 39,628,040 bytes at 49 frames), pass criteria and
latches are those of 112's LAUNCH.md §4. One thing is new: **the verdict action
first waits, for at most 120 s, until all nine qualification previews have been
written**, and requires their preview records. Qualification chunks also write
their previews asynchronously, so the eager, graph and repeat chains all run
with the writer overlapping the next chunk. Byte equality across the three
chains is therefore also evidence that the overlap changes nothing.

## 5. Streaming

The client follows CONTRACT.md with `--packet 113`. Per chunk, the chain's lag is
`timing_s.submit_to_anchor_ready` in the receipt. The MP4's lag is
`timing_s.submit_to_preview_written` in `receipts/preview-<run_name>.json`. The
client logs both and writes the diagnostic border ratio into its manifest lines.

Things to watch in the first chunks (none could be measured on CPU):

- `submit_to_anchor_ready` should be about 4.4 s; 112 had a 4.63 s submit to
  preview written.
- The receipt-to-receipt period should drop by roughly the preview write (about
  0.2–0.25 s) unless the concurrent encode slows the next chunk's CPU-bound
  sampler (see the design note).
- Preview records must arrive in order; `preview_writer.pending` should stay at
  0 or 1.
- **Client poll gap.** On the live 112 receipts, the next submit came 0.41 s
  after each commit (median of 40). That is the client's `--poll 0.5` status
  polling, not the server. `--poll 0.05` should recover about 0.35 s per chunk
  at no server cost.

Experiments with resets: `--reset-every-chunks N` and/or `--reset-on-scene-change`.
Plot `anchor_diagnostics.border_to_centre_chroma_ratio` from the receipts, or from
the client manifest, against `stream_seq` to see drift build up and clear.

Storage per chunk is 112's plus a preview record of about 1 KB.

To stop: one SIGINT (`systemctl --user stop ltx113-stream-server-20261008`),
followed by the usual postflight. A preview queued at that moment may be left
without a record (and with a `.partial` file). Never use a restart loop.
