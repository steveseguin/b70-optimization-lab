# Packet 112 / 113 / 114 continuation stream client

## Packet 113 (`--packet 113`)

The default is still `--packet 112`, and its behaviour is unchanged (46/46 of
`tests/run_tests_112.py`). Against a packet 113 server, add **`--packet 113`**.
That is the only change needed. It does three things:

- It selects the sealed 113 manifest `a23dbc94…f7f28b` and module hashes, and
  the default `--contract-dir` `prepared-continuation-stream-113/resolution/components/`.
  A 112 setting refuses a 113 server at preflight (exit 8), and the reverse also
  holds.
- It applies the 113 bounded wait rule (113 CONTRACT.md §6a). The receipt comes
  before the MP4. The client submits the next chunk as soon as the receipt is
  seen, and only then waits, for at most `--save-wait` (default 10 s), for
  `GET /ltx-stream/preview/<run>`. It checks the MP4's bytes and SHA-256
  against the record, then writes the manifest line. The sink therefore never
  sees an incomplete MP4. A missing record means exit 7. A preview failure
  (`stream-preview-failure-*.json` or 503) means exit 6 or 2.
- It enables the chain-reset options, which are both off by default:
  - `--reset-every-chunks N`: a reset at every `stream_seq` divisible by N.
  - `--reset-on-scene-change`: a reset whenever the scene or its prompt changes.

  A reset chunk is unanchored. Its manifest line has no `skip_first_frames` and
  carries `"reset": true`. 113 manifest lines also carry
  `submit_to_anchor_ready`, `preview_sha256` and the anchor border diagnostic
  (`border_to_centre_chroma_ratio`, `border_mean_chroma`,
  `centre_mean_chroma`) for drift plots.

Tests: `tests/run_tests_113.py` against `tests/fake_comfy113.py` (11/11).

Measured on the live 112 receipts: the next submit followed each commit by a
median of 0.41 s, which is the `--poll 0.5` status-poll interval.
`--poll 0.05` recovers most of that on either packet.

## Packet 114 (`--packet 114`)

Against a packet 114 server, add **`--packet 114`**. The 112 default and
`--packet 113` behave exactly as before. Packet 114 is **not sealed yet**, so
for now the client needs `--manifest-sha256` and `--contract-dir`; without
them it stops with exit 8 before sending anything. After the build, fill in
`PACKET114_MANIFEST_SHA256` and re-check `PACKET114_MODULE_SHA256` near the top
of `ltx_continuation_client.py` (both in one marked block). The module hashes
there were taken from the author's files in
`recovery/20261008-continuation114-stream/` on 2026-10-08.

What it does differently from 113:

- **Anchor mode and chunk length come from the server.** The status route
  says `anchor` (`latent`, the default, or `frame`) and `frames` (49 or 97).
  Every request is built with both. `--expect-anchor` and `--expect-frames 97`
  only guard against the wrong server. Run names start with `stream114-`.
- **Decode record, then preview.** With the latent anchor the server commits
  the receipt before the decode. The client submits the next chunk first, then
  waits for `GET /ltx-stream/decode/<run>` and then
  `GET /ltx-stream/preview/<run>`. It checks both records against the receipt
  and the MP4's bytes and SHA-256 against the preview record. One
  `--save-wait` bound covers both; on 114 its default is **30 s** (a 97-frame
  preview can lag the receipt by a few seconds). Nothing arriving in time is
  exit 7. A failed decode thread (`stream-decode-failure-*.json`, or 503 from
  the decode route) is exit 2. With the frame anchor the decode record exists
  before the receipt.
- **Qualification.** The client re-runs the 114 `qualification_gate.decide`
  over the nine receipts, the nine decode records (fetched from the decode
  route and checked against the hashes the verdict file binds) and the
  server's capture re-reads from the verdict file.
- **Text reuse is on by default on 114 servers.** The client sends
  `reuse_text: 1` exactly when the server requires it: not chunk 0, not a
  reset, same prompt as the chunk before. Otherwise 0.
- **Resets** (`--reset-every-chunks`, `--reset-on-scene-change`) work as on 113.
- **Manifest lines** keep `skip_first_frames: 1` on anchored chunks and leave
  it out on chunk 0 and resets. 114 lines also carry `frames`, `new_frames`,
  `seconds` (new frames / 24, so 2.0 s at 49 frames and 4.0 s at 97),
  `anchor`, `reuse_text`, `last_frame_sha256`, `images_sha256`,
  `submit_to_decode_done`, and the border diagnostic, which now comes from the
  decode record.

Tests: `tests/run_tests_114.py` against `tests/fake_comfy114.py` (26/26 on
2026-10-08). The fake takes `--anchor`, `--frames`, `--text-reuse`,
`--decode-delay`, `--preview-delay` and the fault injections listed in its
docstring.

`ltx_continuation_client.py` drives the packet 112 continuation server
(`recovery/20261008-continuation112-stream/CONTRACT.md`, `LAUNCH.md`). It runs
on the CPU and only talks to the server's HTTP routes. It never starts, stops
or signals the server and never retries a refused request.

It has two phases:

1. **Qualification.** This is on by default. The client sends the 11 requests
   in LAUNCH.md section 4 (window probe, prepare, the eager chain, the
   graph-replay chain, the exact repeat) one after another, each after the
   previous one has finished, and then calls the `qualify-verdict` action once.
   It streams only if all of these hold:
   - the server answers `{"passed": true, "phase": "stream", "qualified_text_windows": [64]}`;
   - `stream-qualification-verdict.json` hashes to the server's verdict digest
     and says passed, with no failures and all four tensors identical for
     chunks 0, 1 and 2;
   - the client's own run of the sealed `qualification_gate.decide()` passes.
     It runs this over the nine committed receipts, which it fetches from
     `/ltx-stream/receipt/<run>`, and the server's capture re-reads.
2. **Streaming.** The client runs one anchor chain for as long as it is left
   running. `stream_seq` 0 is plain text-to-video. Every later chunk names the
   previous chunk's `anchor_out.sha256`. Only one request is ever in the
   server. The next request is built while the current one runs, and it is
   posted in the same poll cycle in which the previous receipt is seen (the
   fake server measured a median of 0.04 s at a 0.05 s poll). Every completed
   chunk adds one line to the sink manifest.

Run it with the venv Python and `-B`:
`/home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py`.
It imports the sealed `stream_contract.py`, `stream_receipts.py` and
`qualification_gate.py` from
`prepared-continuation-stream-112/resolution/components/`. It checks their
SHA-256 against the packet manifest and writes nothing there.

## The command to use

Before you start:

- The server is up and passes LAUNCH.md section 3 (health and identity).
- No other client has sent it anything.
- `<PL>` is the placement you launched with: `two-way20-28` (the
  recommendation in LAUNCH.md section 0) or `two-way`.

Run it as a user unit so that the agent harness cannot kill it, and so that a
stop sends SIGINT. On SIGINT the client finishes the chunk in flight and then
exits:

```bash
mkdir -p /home/steve/ltx-stream/s112-stream01
systemd-run --user --unit=ltx112-stream-client --property=Restart=no \
  --property=KillSignal=SIGINT --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py \
    --work-dir /home/steve/ltx-stream/s112-stream01 \
    --expect-frames 49 --expect-placement <PL> --expect-text-reuse 0 \
    --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
    --sink-stats /home/steve/ltx-stream/s112-stream01/sink-stats.json \
    --max-ahead-seconds 60 --delete-consumed-previews
```

Follow it with `journalctl --user -u ltx112-stream-client -f`. The unit's exit
status is the halt code listed below. Stop it with
`systemctl --user stop ltx112-stream-client`; the client finishes the chunk in
flight, writes its state and exits 0.

**Two-step form.** Use this to look at the verdict before any streaming:

1. Run the same command with `--qualification-only`. It exits 0 after the
   verdict passes and is verified.
2. Run it again with `--skip-qualification`. On a server that has already
   qualified, the default mode also just verifies the verdict and streams.

**Sink for this lane.** This is `start-sink.sh` with the s112 paths:

```bash
W=/home/steve/ltx-stream/s112-stream01
/home/steve/.venvs/ltx25-baseline/bin/python -B ltx_rtmp_sink.py --manifest $W/manifest.jsonl \
  --rtmp rtmp://127.0.0.1:1935/live/local --state $W/sink-state.json --stats $W/sink-stats.json \
  --workdir $W/sinkwork --size 768x768 --title "..."
```

Leave out the sink's own `--delete-played-after-seconds` and
`--disposable-dir-regex` for this lane. That sink option removes whole
directories with `rmtree`. The client's `--delete-consumed-previews` deletes
only the MP4 named in each receipt, which is all that CONTRACT.md section 8
allows.

## Files in the work dir

| file | content |
|---|---|
| `manifest.jsonl` | One line per chunk, for the sink. The sink's fields (`seq`, `path`, `generated_utc`, `label`, `index` = `stream_seq`) plus `skip_first_frames: 1` on anchored chunks, `scene`, `stream_seq`, `seed`, `anchor_sha256` (this chunk's `anchor_out`), `predecessor_anchor_sha256`, `submit_to_preview_written` (from the receipt's `timing_s`), `run_name`, `prompt_id`, `new_frames`, `schedule_pos` and `server_identity_sha256`. |
| `client-state.json` | Written atomically: server identity, schedule origin, next manifest seq, the pending request, previews not yet disposed of, and the last stop reason. |
| `qualification.jsonl` | One row per qualification request, plus the verdict response. |

Each chunk prints one log line with these fields: `seq`, `stream_seq`,
`scene`, `seed`, submit to preview time, the stage times from the receipt's
`timing_ns` (queue, text plus prep, sampler A, sampler B, decode, preview) and
the first 12 characters of the anchor hash.

## Flags

| flag | default | meaning |
|---|---|---|
| `--work-dir` | required | where the manifest, state and logs go; must not be under `prepared-*` |
| `--manifest`, `--state` | `WORK/manifest.jsonl`, `WORK/client-state.json` | |
| `--scenes` | `data/stream/kittens-01.json` | `[{"id","prompt","chunks"}]`, `{"scenes": [...]}`, or the `{"fixtures": [{"id","prompt",...}]}` format; the list repeats forever |
| `--default-chunks` | 4 | chunks for a scene without `chunks`; 4 chunks are about 8 s at 49 frames |
| `--base-seed` | 11200000 | seed = base + `stream_seq` |
| `--skip-qualification` / `--qualification-only` | off | see above |
| `--expect-frames/-placement/-text-reuse` | unset | refuse (exit 8) if the server differs |
| `--token-check` | `exact` | `exact` counts Gemma tokens; `off` leaves the check to the server |
| `--sink-stats`, `--max-ahead-seconds` | unset, 60 | throttle on the sink's `last_played_seq` |
| `--delete-consumed-previews`, `--dispose-margin` | off, 50 | delete a chunk's MP4 once the sink has played 50 manifest seqs past it |
| `--min-free-gib` | 52 | free space below this under the results root means exit 9 |
| `--http-fail-seconds` | 120 | how long HTTP may fail before exit 5 |
| `--chunk-timeout` | 900 | limit from submit to receipt (the qualify driver's chunk limit) |
| `--save-wait` | 10 | how long to wait for a receipt's MP4 to appear |
| `--recover-max` | 8 | how many completed chunks to recover when this manifest has no record of the server |
| `--poll` | 0.5 | status poll interval in seconds |
| `--max-chunks` | 0 | clean stop after N chunks (0 means run forever) |
| `--port`, `--root`, `--contract-dir`, `--manifest-sha256` | live values | tests only; on port 8188 the client requires the sealed contract dir |

## Exit codes

| code | cause |
|---|---|
| 0 | clean stop (SIGINT/SIGTERM after the chunk in flight, `--max-chunks`, `--qualification-only`) |
| 2 | server halted: status `halted`, or HTTP 503 `halted` |
| 4 | `FAULT.json` under the results root |
| 5 | HTTP failing for more than `--http-fail-seconds`, or a POST whose outcome is unknown |
| 6 | failed-job receipt: `stream-failure-<run>.json` in the server run dir |
| 7 | preview MP4 missing, empty, a different size from the receipt, or outside `<output>/<run_name>/` |
| 8 | preflight refused: manifest/identity/frames/placement, module hashes, or a schedule or prompt that fails the check |
| 9 | disk below `--min-free-gib` |
| 10 | refused with 409 `order` or `stale-anchor` |
| 11 | refused with `contract`, `missing-client-id` or `missing-prompt-id` (HTTP 400, or 409 `contract`) |
| 12 | a receipt or the sequence does not match the request (wrong anchor, prompt, seed or digest; `next_stream_seq` moved past ours, meaning another client is submitting) |
| 13 | qualification failed or did not pass (including a verdict the client cannot re-derive) |
| 14 | refused with `text-reuse-rule`, `text-cache-missing`, `window-not-captured` or `window-not-qualified` |
| 15 | refused with `busy`, `not-streaming`, `not-prepared`, `storage`, `precheck-error`, or an unknown code |
| 16 | a request was not committed within its time limit (900 s per chunk; 1800 s per setup request) |
| 130 | a second signal while waiting |

After any non-zero exit, do not start the client again until you have looked
at the server's evidence. A 409 refusal does not latch the server, but this
client still stops on one.

## Restarts

- **Same server.** The client reads `next_stream_seq` and
  `chain.anchor_sha256` from `/ltx-stream/status` and does not trust its own
  state. If a chunk of its own is still running (the client crashed), it takes
  that chunk over. For any committed chunk that has no line in the manifest,
  it fetches the receipt and writes the line. Then it continues on the
  server's last anchor. The schedule position comes from the state file, or
  from the `schedule_pos` of this server's manifest lines.
- **New server** (a different `server_identity_sha256`). The chain starts again
  at `stream_seq` 0, which is unanchored, and the manifest `seq` keeps
  counting up. The schedule starts at the beginning of the scene after the
  last one played.

## Decisions on points the contract leaves open

1. **How completion is detected.** The client polls `GET /ltx-stream/status`
   until `next_stream_seq == n+1` and `active == null`, then fetches the
   receipt from the receipt route. It does not use the WebSocket. The server
   writes the receipt file before it clears `active`, so a client that posted
   as soon as the receipt appeared could get `busy`. The status route is read
   under the authority lock, so polling it avoids that.
2. **`busy` is a halt (exit 15), not a retry.** With the check in point 1 it
   should not happen. If it does, something else is using the server.
3. **The text-window check counts real tokens.** The server's rule is the
   smallest bucket in (64, 128, 256, 512, 1024) that holds the real token
   count, BOS included. The client counts BOS plus the Gemma tokenizer's
   `encode(text, add_special_tokens=False)`, using the `tokenizer_json` stored
   inside the text encoder's own safetensors and the venv's `tokenizers`
   package. That package is the only part of the client outside the standard
   library. A prompt over 64 tokens refuses the whole schedule at startup.
   Prompts with a backslash or `embedding:` are also refused, because ComfyUI's
   escape and embedding parsing would change the count. The kitten prompts
   come to 45–51 tokens and the qualification prompts to 56 and 48. Use
   `--token-check off` if the tokenizer is not available; the server then
   refuses over-long prompts itself, without a latch, and the client exits 14.
4. **Qualification includes the two setup requests** (window probe and
   prepare), because the server refuses anything else first. If a previous run
   was interrupted, the client continues from the server's
   `completed_fixed_requests`. Each request is still sent exactly once.
5. **A verdict counts only if the client can re-derive it.** That means
   `passed: true`, the file digest, and the client's own run of
   `qualification_gate.decide`, as described above. Any mismatch exits 13.
6. **Scene ids are cleaned up for the server.** `scene_id` must match
   `[a-z0-9]{1,32}`, so fixture ids such as `kitten-yawn` become `kittenyawn`.
7. **Seeds are exactly `--base-seed + stream_seq`.** `stream_seq` starts at 0
   again on a new server, so seeds repeat from one server launch to the next.
   The scenes do not repeat, because the schedule continues at the next scene.
8. **`reuse_text`** is 1 only when the server has `text_reuse == 1`, the chunk
   is not chunk 0, and the prompt's SHA-256 equals the predecessor's
   `prompt_sha256` (taken from the receipt, or from `chain.prompt_sha256` on a
   restart).
9. **Manifest fields.** `anchor_sha256` is this chunk's `anchor_out`.
   `skip_first_frames` comes from the receipt's `delivery.drop_leading_frames`
   and is left out for chunk 0. `index` is `stream_seq`.
10. **Disposal.** The client deletes only the MP4 path from the receipt, and
    only if it matches `<output>/stream112-s\d{8}/preview_\d{5}_.mp4`, is not
    a symlink and is in a directory that is not a symlink. It then removes the
    directory only if it is empty. The margin is counted in manifest seqs.
11. **Preview checks.** The path must be `<output>/<run_name>/preview_NNNNN_.mp4`
    and the file size must equal `preview.bytes`. The receipt is committed only
    after the preview is written, so the client waits at most `--save-wait`.
12. **Integrity checks on receipts.** Each receipt must pass
    `stream_receipts.validate_receipt`. Its SHA-256 must match the server's
    `last_stream_receipts` record. Its anchor, prompt, seed, scene and
    prompt_id must match the request. The status `chain` must end at this
    receipt.
13. **The throttle counts 2.0 s per chunk** (48 new frames). Chunk 0 is
    0.04 s longer.
14. **A refused POST connection is held** for up to `--http-fail-seconds`,
    because nothing was sent; this matches the existing driver. Any other POST
    failure exits 5 straight away.

## Sink change

`ltx_rtmp_sink.py` now reads an optional `skip_first_frames` field on a
manifest line. It drops that many leading video frames and the matching
`k × 2000` audio samples (k/24 s), after the clip's audio has been padded or
trimmed to its frame count. A line without the field is decoded exactly as
before.

Checked on 20 real preview clips by comparing the old file (a scratch copy)
with the new one:

- `decode_clip` without the field gave byte-identical frames and audio for
  20/20 clips.
- With `skip_first_frames: 1` the result equaled the old `frames[1:]` and
  `audio[2000*4:]`.

An end-to-end `--out` run at `--speed 8` used a manifest of 20 lines,
alternating lines with and without the field. It played all 20 clips at
25/24/25/24… frames, 490 clip frames plus 78 hold frames = 568 frames in the
FLV, and exited 0.

## Tests

```bash
cd /home/steve/llm-optimizations/experiments/ltx25-b70/stream
/home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_112.py   # port 18189, about 2 minutes
```

`tests/fake_comfy112.py` implements the contract's routes, receipts (they pass
`validate_receipt`), admission refusals and a verdict decided by the sealed
`qualification_gate`. It has fault injections, listed in its docstring. Result
on 2026-10-08: 46/46 passed.

## Open questions for the owner

- **Audio seam.** CONTRACT.md section 6 defines no audio alignment rule. A
  49-frame chunk has 96,480 samples. After the 2,000 samples for the dropped
  frame, 94,480 remain against 96,000 for 48 frames, so the sink pads about
  32 ms of silence at the end of every continuation chunk. A crossfade or trim
  rule is yours to decide.
- **Placement** (`two-way` or `two-way20-28`, LAUNCH.md section 0). The client
  reads it from the server; `--expect-placement` only guards against the wrong
  one.
- **Seeds repeating across server launches** (decision 7). Change
  `--base-seed` on each launch if that matters.
