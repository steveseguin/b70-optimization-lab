# LTX live-stream sink

`ltx_rtmp_sink.py` turns an ordered, growing sequence of short MP4 clips into one
continuous 24 fps live stream (RTMP, e.g. Twitch / meshcast `rtmp://host/app/key`,
or a local FLV for testing). CPU only: PyAV decodes, one long-lived ffmpeg
subprocess encodes (libx264 veryfast/zerolatency, 2500k CBR-ish, 2 s GOP, AAC 128k).

Run with the venv that has PyAV:

```bash
PY=/home/steve/.venvs/ltx25-baseline/bin/python
$PY ltx_rtmp_sink.py --manifest /path/clips.jsonl --rtmp rtmp://host/app/streamkey \
    --state /path/sink-state.json --stats /path/sink-stats.json \
    --title "LTX-2.5 live on 4x Intel Arc Pro B70 · 256² native, batch-2 lane · each clip freshly generated"
# local test: --out /path/test.flv  (add --speed 8 to run faster than real time; test only)
```

## Manifest format

JSON Lines, appended by the generator, one line per *finished* clip, in playback order:

```json
{"seq": 1, "path": "/abs/path/preview_00001_.mp4", "generated_utc": "2026-10-08T00:50:12Z", "label": "boat seed 42", "index": 26880123}
```

`seq` must increase; lines with `seq <=` the last played/queued seq are ignored
(resume, duplicates). The sink polls every 0.2 s and tolerates a partially
written last line. Write the clip file completely before appending its line.
A clip that cannot be decoded after ~2 s of retries is logged and skipped.

## Behaviour

- Timeline: every output tick is exactly one video frame plus 2000 audio samples
  (48000/24), so A/V cannot drift. Clip audio is resampled to s16 stereo 48 kHz
  and padded/trimmed to the clip's video length. Any input size is scaled with
  lanczos into `--size` (default 768x768) and letterboxed; non-24 fps input is
  retimed to 24 fps.
- Pacing: wall-clock real time (`--speed` > 1 only for tests). If ffmpeg blocks,
  the sink waits and re-anchors its clock (counted as `slips`), never bursting.
- Starvation: when no next clip is ready, the last frame is held with silence and
  the overlay shows `buffering… generator behind by N.N s`. Nothing is ever looped,
  replayed or skipped. `--max-ahead-seconds` only logs a warning; it never skips.
- Overlay (disable with `--no-overlay`): DejaVu Sans via drawtext `textfile=` +
  `reload=1`, rewritten atomically per clip: the `--title` line plus
  `clip <seq> · <label> · generated HH:MM:SS UTC · stream lag N.N s · buffered N clips`
  (lag = now − generated_utc when the clip starts playing).
- Resume: `--state` holds `last_played_seq` (written after each complete clip).
  `--start-seq N` overrides it. SIGINT/SIGTERM finishes the current clip, then
  flushes pipes, waits for ffmpeg and writes state; a second signal stops at once.
- Reconnect: if ffmpeg exits (e.g. RTMP disconnect) the sink logs it, waits 5 s and
  starts a new ffmpeg from the current position (client reconnect only). With
  `--out`, later segments go to `FILE.r1.flv`, `FILE.r2.flv`, ...
- `--stats`: JSON rewritten every 5 s (played_clips, holds, total_hold_seconds,
  last_hold_seconds, current_lag_seconds, ffmpeg_alive, ffmpeg_restarts, buffered_clips, ...).
- Disposal: off by default. `--delete-played-after-seconds N --disposable-dir-regex RE`
  deletes a played clip's parent directory only if its basename fully matches RE.
- Work files (audio FIFO, overlay text) live in `--workdir` (default: a mkdtemp dir).
- CPU: about 0.9 core total at 768x768 1x (python ~0.47, ffmpeg ~0.45), RSS ~280 MB.
  `--decode-threads` (default 2) only matters for faster-than-real-time tests.
