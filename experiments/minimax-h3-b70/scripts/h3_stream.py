#!/usr/bin/env python3
"""Stream finished MiniMax-H3 clips to an RTMP (Twitch, meshcast.io) and/or WHIP endpoint, forever.

What it does
------------
The generator (`smoke_h3.sh duet` with a prompts file, or any `run_h3_t2v.py` run) writes one
`<run>/clip-NN/clip.mp4` and then, last, its `receipt.json`. This tool watches one or more
directories for such pairs and turns them into one never-ending live feed:

* a clip counts as finished only when its `receipt.json` parses, and, when the receipt carries
  `clip_mp4_sha256` (every receipt since 2026-10-03), when clip.mp4's SHA-256 equals it. A half
  written mp4 is never opened.
* a newly finished clip plays next (right after the clip on air ends, or at once with
  `--interrupt`); otherwise the feed loops the most recent `--keep-last N` clips. Before the first
  clip exists it shows a black "waiting" slate with silence, so the destination never sees a gap.
* clip.mp4 is decoded with PyAV into its exact frames (rgb24) and audio (resampled to 48 kHz
  stereo s16) and handed, paced to the wall clock at `--fps`, over two pipes to ONE long-lived
  ffmpeg CLI encoder: libx264 (CBR, `-bf 0`, keyframe every `--keyint-seconds`, baseline profile
  by default) + AAC, with an optional drawtext caption that changes with the clip on air.
* `-f tee` fans the one encode out to every destination: each `--rtmp-url` (flv), an optional
  `--test-sink` (local file or local RTMP listener), and for `--whip-url` an mpegts copy with an
  Opus track that a PyAV thread remuxes into FFmpeg 8's `whip` muxer (the apt ffmpeg here is 6.1
  and has no whip muxer; the venv's PyAV 18.1 links FFmpeg 8 libs that do).
* if the encoder exits (network drop, server restart) it is restarted after `--restart-delay`
  seconds and the feed carries on from the next clip.

Lossless rule
-------------
Generation is untouched: the tool only reads clip.mp4 files the pipeline already wrote. The frames
on air are the exact decoded frames of clip.mp4 (no scaling when `--size` equals the clip size,
which is the default). The transport encode (x264 CBR, AAC/Opus) is lossy, as any live stream is;
the receipts' tensor hashes remain the exactness record.

Limits
------
* Cadence: the lossless stack makes one 5.17 s clip every ~397 s (8-clip soak 2026-10-04), so the
  feed is mostly the last N clips on repeat, with a new one about every 6.5 minutes.
* Clips of a different size than `--size` are scaled to fit and letterboxed (that frame is then
  no longer pixel-exact; keep one resolution per stream).
* meshcast.io: its RTMP-to-WHEP viewer plays video only (no audio), and it needs B-frames off
  (always off here). WHIP needs H.264 constrained baseline + Opus; tested only for argument
  plumbing here, not against a live WHIP server.
* Twitch: rtmp://<ingest>/app/<stream key>, H.264 + AAC, keyframe every 2 s, CBR, <= 6000 kbps.
* CPU: one x264 veryfast encode at 960x544 24 fps (well under one core) plus PyAV decode.

Usage (run with the venv python, which has PyAV)
-----
  PY=/mnt/fast-ai/venvs/minimax-h3/bin/python
  # live, Twitch (key from the environment, never on the command line history if avoidable)
  H3_STREAM_RTMP_URL="rtmp://live.twitch.tv/app/$TWITCH_KEY" \\
      $PY h3_stream.py --watch-dir /mnt/fast-ai/bench-results/minimax-h3
  # meshcast: RTMP server + key from its page, or its WHIP URL (+ optional bearer token)
  $PY h3_stream.py --watch-dir ... --rtmp-url "$MESHCAST_RTMP/$MESHCAST_KEY"
  $PY h3_stream.py --watch-dir ... --whip-url "$MESHCAST_WHIP_URL" [--whip-token T]
  # dry run without any key: local listener in another shell, then
  ffmpeg -listen 1 -i rtmp://127.0.0.1:19350/live/test -t 20 -f null -
  $PY h3_stream.py --clips some/clip.mp4 --test-sink rtmp://127.0.0.1:19350/live/test --duration 20
  # or a file: --test-sink /tmp/out.flv ; just print the ffmpeg command: --dry-run

Destinations may also come from the environment: H3_STREAM_RTMP_URL (several separated by
whitespace), H3_STREAM_WHIP_URL, H3_STREAM_WHIP_TOKEN. Stream keys are redacted in all logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pathlib
import shlex
import signal
import subprocess
import sys
import threading
import time

LOG = logging.getLogger("h3_stream")
DEFAULT_CAPTION = "generated on 2 x Intel Arc Pro B70, lossless"
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
AUDIO_RATE = 48000


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------


def redact(url: str) -> str:
    """Hide the stream key (last path component / query) of an ingest URL for logs."""
    if "://" not in url:
        return url
    head, _, tail = url.rpartition("/")
    if not head.split("://", 1)[1].count("/"):  # no path at all
        return url
    return f"{head}/***" if tail else url


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_size(text: str | None):
    if not text or text == "auto":
        return None
    w, h = text.lower().split("x")
    w, h = int(w), int(h)
    if w % 2 or h % 2:
        raise SystemExit("--size needs even width and height (yuv420p)")
    return w, h


def ff_escape(value: str) -> str:
    """Escape a value for use inside an ffmpeg filter option."""
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


# ------------------------------------------------------------------------------------------------
# clip discovery
# ------------------------------------------------------------------------------------------------


class Clip:
    def __init__(self, mp4: pathlib.Path, receipt: dict | None, stamp: float):
        self.mp4 = mp4
        self.receipt = receipt or {}
        self.stamp = stamp

    @property
    def label(self) -> str:
        parent = self.mp4.parent
        return f"{parent.parent.name}/{parent.name}" if parent.name.startswith("clip-") else parent.name

    def caption(self, extra: str, prompt_chars: int) -> str:
        lines = [self.label]
        prompt = self.receipt.get("prompt")
        if prompt_chars > 0 and isinstance(prompt, str) and prompt:
            lines.append(prompt if len(prompt) <= prompt_chars else prompt[: prompt_chars - 3] + "...")
        if extra:
            lines.append(extra)
        return "\n".join(lines)


class Watcher:
    """Finds finished clips: `clip.mp4` beside a parseable `receipt.json` whose digest matches."""

    def __init__(self, dirs, explicit, depth: int, verify: bool):
        self.dirs = [pathlib.Path(d) for d in dirs]
        self.explicit = [pathlib.Path(p) for p in explicit]
        self.depth = depth
        self.verify = verify
        self.known: dict[pathlib.Path, Clip] = {}
        self.rejected: dict[pathlib.Path, tuple] = {}  # path -> (receipt mtime, mp4 size) last refused

    def _candidates(self):
        for d in self.dirs:
            for level in range(self.depth + 1):
                yield from d.glob("/".join(["*"] * level + ["receipt.json"]))
        for mp4 in self.explicit:
            yield mp4.parent / "receipt.json" if (mp4.parent / "receipt.json").exists() else mp4

    def _accept(self, item: pathlib.Path):
        if item.suffix == ".mp4":  # explicit clip without a receipt: take it as is
            st = item.stat()
            return Clip(item, None, st.st_mtime)
        mp4 = item.parent / "clip.mp4"
        if not mp4.exists():
            return None
        r_st, m_st = item.stat(), mp4.stat()
        key = (r_st.st_mtime_ns, m_st.st_size, m_st.st_mtime_ns)
        if self.rejected.get(mp4) == key:
            return None
        try:
            receipt = json.loads(item.read_text())
        except (OSError, ValueError):
            return None  # receipt still being written; try again next scan
        want = receipt.get("clip_mp4_sha256")
        if self.verify and want and sha256_file(mp4) != want:
            LOG.warning("skip %s: clip.mp4 digest differs from its receipt", mp4)
            self.rejected[mp4] = key
            return None
        if not want and time.time() - m_st.st_mtime < 5:  # pre-2026-10-03 receipt: wait for size to settle
            return None
        return Clip(mp4, receipt, r_st.st_mtime)

    def scan(self) -> list[Clip]:
        """Return newly finished clips, oldest first."""
        new = []
        for item in self._candidates():
            mp4 = item if item.suffix == ".mp4" else item.parent / "clip.mp4"
            if mp4 in self.known:
                continue
            try:
                clip = self._accept(item)
            except FileNotFoundError:
                continue
            if clip is not None:
                self.known[mp4] = clip
                new.append(clip)
        new.sort(key=lambda c: (c.stamp, str(c.mp4)))
        return new


# ------------------------------------------------------------------------------------------------
# decoding a clip into paced raw frames + audio
# ------------------------------------------------------------------------------------------------


def decode_clip(path: pathlib.Path, size, fps: int):
    """-> (list of rgb24 HxWx3 uint8 arrays at `size`, s16 interleaved stereo bytes at 48 kHz)."""
    import av
    import numpy as np

    frames, pcm = [], []
    with av.open(str(path)) as container:
        vstreams = container.streams.video
        astreams = container.streams.audio
        resampler = av.AudioResampler(format="s16", layout="stereo", rate=AUDIO_RATE)
        streams = [s for s in (vstreams[:1] + astreams[:1])]
        for frame in container.decode(*streams):
            if isinstance(frame, av.VideoFrame):
                frames.append(fit(frame, size))
            else:
                for out in resampler.resample(frame):
                    pcm.append(out.to_ndarray().reshape(-1))
        if astreams:
            for out in resampler.resample(None):
                pcm.append(out.to_ndarray().reshape(-1))
    audio = np.concatenate(pcm).astype("<i2") if pcm else np.zeros(0, "<i2")
    return frames, audio


def fit(frame, size):
    """Exact frame when sizes match; otherwise scale to fit and letterbox (not pixel-exact)."""
    import numpy as np

    w, h = size
    if frame.width == w and frame.height == h:
        return frame.to_ndarray(format="rgb24")
    scale = min(w / frame.width, h / frame.height)
    sw, sh = max(2, int(frame.width * scale) // 2 * 2), max(2, int(frame.height * scale) // 2 * 2)
    small = frame.reformat(width=sw, height=sh, format="rgb24").to_ndarray()
    canvas = np.zeros((h, w, 3), np.uint8)
    y, x = (h - sh) // 2, (w - sw) // 2
    canvas[y : y + sh, x : x + sw] = small
    return canvas


# ------------------------------------------------------------------------------------------------
# the encoder process
# ------------------------------------------------------------------------------------------------


def build_ffmpeg(args, size, vfd: int | str, afd: int | str, caption_file: pathlib.Path):
    """The ffmpeg CLI argv for one long-lived encoder; returns (argv, has_whip_pipe)."""
    w, h = size
    gop = max(1, round(args.fps * args.keyint_seconds))
    cmd = [args.ffmpeg, "-hide_banner", "-loglevel", args.ffmpeg_loglevel, "-nostdin",
           "-thread_queue_size", "512", "-probesize", "32", "-analyzeduration", "0", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-video_size", f"{w}x{h}", "-framerate", str(args.fps), "-i", f"pipe:{vfd}",
           "-thread_queue_size", "512", "-probesize", "32", "-analyzeduration", "0", "-f", "s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
           "-i", f"pipe:{afd}"]
    vf = []
    if args.overlay_text is not None and args.font and pathlib.Path(args.font).exists():
        vf.append(
            "drawtext=fontfile='{}':textfile='{}':reload=1:fontsize={}:fontcolor=white:"
            "line_spacing=4:box=1:boxcolor=black@0.55:boxborderw=6:x=10:y=h-th-12".format(
                ff_escape(args.font), ff_escape(str(caption_file)), args.font_size))
    elif args.overlay_text is not None:
        LOG.warning("font %s not found: no caption", args.font)
    vf.append("format=yuv420p")
    cmd += ["-map", "0:v", "-map", "1:a", "-vf", ",".join(vf),
            "-c:v", "libx264", "-preset", args.preset, "-tune", "zerolatency",
            "-profile:v", args.profile, "-bf", "0", "-g", str(gop), "-keyint_min", str(gop),
            "-sc_threshold", "0", "-b:v", f"{args.video_kbps}k", "-minrate", f"{args.video_kbps}k",
            "-maxrate", f"{args.video_kbps}k", "-bufsize", f"{args.video_kbps * 2}k",
            "-x264-params", "nal-hrd=cbr", "-pix_fmt", "yuv420p"]
    if args.level:
        cmd += ["-level:v", args.level]
    cmd += ["-c:a:0", "aac", "-b:a:0", f"{args.audio_kbps}k", "-ar", str(AUDIO_RATE), "-ac", "2"]
    whip = bool(args.whip_url)
    if whip:  # a second audio track, Opus, for WebRTC
        cmd += ["-map", "1:a", "-c:a:1", "libopus", "-b:a:1", f"{args.audio_kbps}k"]
    slaves = []
    for url in args.rtmp_urls:
        slaves.append(f"[f=flv:select=\\'v:0,a:0\\':onfail=ignore:flvflags=no_duration_filesize]{url}")
    if args.test_sink:
        sink = args.test_sink
        if sink.startswith(("rtmp://", "rtmps://")):
            slaves.append(f"[f=flv:select=\\'v:0,a:0\\':onfail=ignore:flvflags=no_duration_filesize]{sink}")
        else:
            fmt = {".flv": "flv", ".ts": "mpegts", ".mkv": "matroska"}.get(pathlib.Path(sink).suffix, "matroska")
            slaves.append(f"[f={fmt}:select=\\'v:0,a:0\\']{sink}")
    if whip:
        slaves.append("[f=mpegts:select=\\'v:0,a:1\\']pipe:1")
    if not slaves:
        raise SystemExit("no destination: give --rtmp-url, --whip-url or --test-sink (or H3_STREAM_* env)")
    cmd += ["-flags", "+global_header", "-f", "tee", "|".join(slaves)]
    return cmd, whip


def redact_cmd(cmd) -> str:
    out = []
    for part in cmd:
        if "rtmp" in part and "]" in part:
            part = "|".join(seg.split("]", 1)[0] + "]" + redact(seg.split("]", 1)[1]) for seg in part.split("|"))
        out.append(part)
    return shlex.join(out)


def whip_forwarder(src, url: str, token: str | None, stop: threading.Event):
    """Remux the encoder's mpegts (H.264 + Opus) into PyAV's whip muxer (FFmpeg 8)."""
    import av

    try:
        inp = av.open(src, mode="r", format="mpegts")
        opts = {"authorization": token} if token else {}
        out = av.open(url, mode="w", format="whip", options=opts)
        mapping = {}
        for s in inp.streams:
            if s.type in ("video", "audio"):
                mapping[s.index] = out.add_stream_from_template(s)
        for packet in inp.demux(*[inp.streams[i] for i in mapping]):
            if stop.is_set():
                break
            if packet.dts is None:
                continue
            packet.stream = mapping[packet.stream.index]
            out.mux(packet)
        out.close()
    except Exception as exc:  # noqa: BLE001 - a WHIP failure must not stop RTMP
        LOG.error("WHIP forwarder stopped: %s", exc)
        try:  # keep draining so the encoder never blocks on the pipe
            while src.read(1 << 16):
                pass
        except Exception:  # noqa: BLE001
            pass


class EncoderStalled(Exception):
    pass


class _PipeWriter(threading.Thread):
    """Feeds one encoder input pipe from a bounded queue, so a slow or still-probing encoder input
    never blocks the other pipe (ffmpeg opens its inputs one after another)."""

    def __init__(self, fd: int, depth: int):
        super().__init__(daemon=True)
        import queue

        try:
            import fcntl

            fcntl.fcntl(fd, 1031, 1 << 20)  # F_SETPIPE_SZ: 1 MiB pipe buffer
        except OSError:
            pass
        self.fh = os.fdopen(fd, "wb", buffering=0)
        self.q = queue.Queue(maxsize=depth)
        self.error = None
        self.start()

    def run(self):
        try:
            while True:
                item = self.q.get()
                if item is None:
                    break
                self.fh.write(item)
        except OSError as exc:
            self.error = exc
        finally:
            try:
                self.fh.close()
            except OSError:
                pass

    def put(self, item, timeout):
        import queue

        if self.error is not None:
            raise BrokenPipeError(self.error)
        try:
            self.q.put(item, timeout=timeout)
        except queue.Full:
            raise EncoderStalled(f"encoder input stalled for {timeout:.0f} s") from None


class Encoder:
    def __init__(self, args, size, caption_file):
        self.args, self.size, self.caption_file = args, size, caption_file
        self.proc = None
        self.stop = threading.Event()

    def start(self):
        vr, vw = os.pipe()
        ar, aw = os.pipe()
        cmd, whip = build_ffmpeg(self.args, self.size, vr, ar, self.caption_file)
        LOG.info("encoder: %s", redact_cmd(cmd))
        self.proc = subprocess.Popen(cmd, pass_fds=(vr, ar), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE if whip else subprocess.DEVNULL)
        os.close(vr)
        os.close(ar)
        depth = max(2, self.args.fps)  # about one second of frames queued per pipe
        self.video = _PipeWriter(vw, depth)
        self.audio = _PipeWriter(aw, depth)
        if whip:
            self.stop.clear()
            threading.Thread(target=whip_forwarder, daemon=True,
                             args=(self.proc.stdout, self.args.whip_url, self.args.whip_token, self.stop)).start()

    def write(self, rgb, pcm_bytes):
        if self.proc.poll() is not None:
            raise BrokenPipeError(f"encoder exited rc={self.proc.returncode}")
        self.audio.put(pcm_bytes, self.args.stall_seconds)
        self.video.put(rgb.tobytes(), self.args.stall_seconds)

    def close(self, timeout=10, kill=False):
        self.stop.set()
        if kill and self.proc and self.proc.poll() is None:
            self.proc.kill()
        for w in (getattr(self, "audio", None), getattr(self, "video", None)):
            if w is not None:
                try:
                    w.q.put(None, timeout=timeout)
                except Exception:  # noqa: BLE001
                    pass
        if self.proc:
            try:
                self.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode if self.proc else None


# ------------------------------------------------------------------------------------------------
# main loop
# ------------------------------------------------------------------------------------------------


def write_caption(path: pathlib.Path, text: str):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)  # drawtext re-reads it every frame; the rename keeps every read whole


def slate(size):
    import numpy as np

    return np.full((size[1], size[0], 3), 16, np.uint8)


def run(args) -> int:
    import numpy as np

    watcher = Watcher(args.watch_dir, args.clips, args.depth, not args.no_verify)
    playlist: list[Clip] = []
    pending: list[Clip] = []
    first = watcher.scan()
    playlist = first[-args.keep_last :]
    LOG.info("found %d finished clip(s); looping the last %d", len(first), len(playlist))
    size = parse_size(args.size)
    if size is None and playlist:
        import av

        with av.open(str(playlist[-1].mp4)) as c:
            cc = c.streams.video[0].codec_context
            size = (cc.width, cc.height)
    size = size or (960, 544)
    LOG.info("output %dx%d @ %d fps, video %d kbps, audio %d kbps", *size, args.fps, args.video_kbps, args.audio_kbps)

    caption_file = pathlib.Path(args.state_dir) / "h3_stream_caption.txt"
    caption_file.parent.mkdir(parents=True, exist_ok=True)
    write_caption(caption_file, "waiting for the first clip\n" + (args.overlay_text or ""))

    if args.dry_run:
        cmd, _ = build_ffmpeg(args, size, 3, 4, caption_file)
        print(redact_cmd(cmd) if not args.show_secrets else shlex.join(cmd))
        print(f"# clips that would loop now ({len(playlist)}):")
        for c in playlist:
            print(f"#   {c.mp4}")
        return 0

    samples_per_frame = AUDIO_RATE / args.fps
    stop_at = time.monotonic() + args.duration if args.duration else None
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())

    encoder = Encoder(args, size, caption_file)
    encoder.start()
    t0 = time.monotonic()
    n = 0  # frames sent on this encoder
    loop_pos = 0
    last_scan = 0.0
    cache: dict[pathlib.Path, tuple] = {}

    def send(rgb, pcm):
        nonlocal n, t0, encoder
        delay = t0 + n / args.fps - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif delay < -2.0:  # fell behind (slow decode): re-anchor rather than burst
            t0 = time.monotonic() - n / args.fps
        try:
            encoder.write(rgb, pcm)
            n += 1
            return True
        except (BrokenPipeError, OSError, EncoderStalled) as exc:
            rc = encoder.close(timeout=2, kill=True)
            LOG.error("encoder failed (%s, rc=%s); restarting in %.0f s", exc, rc, args.restart_delay)
            time.sleep(args.restart_delay)
            encoder = Encoder(args, size, caption_file)
            encoder.start()
            t0, n = time.monotonic(), 0
            return False

    def done():
        return stopping.is_set() or (stop_at is not None and time.monotonic() >= stop_at)

    while not done():
        if time.monotonic() - last_scan >= args.scan_seconds:
            last_scan = time.monotonic()
            for clip in watcher.scan():
                LOG.info("new clip finished: %s", clip.mp4)
                pending.append(clip)
        if pending:
            clip = pending.pop(0)
            playlist.append(clip)
            playlist = playlist[-args.keep_last :]
            loop_pos = len(playlist)  # after the new clip, the loop starts over from the oldest kept
        elif playlist:
            clip = playlist[loop_pos % len(playlist)]
            loop_pos += 1
        else:  # nothing yet: one second of slate + silence, then look again
            silence = bytes(int(samples_per_frame) * 4)
            for _ in range(args.fps):
                if done() or not send(slate(size), silence):
                    break
            continue

        if clip.mp4 not in cache:
            try:
                cache[clip.mp4] = decode_clip(clip.mp4, size, args.fps)
            except Exception as exc:  # noqa: BLE001
                LOG.error("cannot decode %s: %s", clip.mp4, exc)
                playlist = [c for c in playlist if c.mp4 != clip.mp4]
                continue
            keep = {c.mp4 for c in playlist} | {c.mp4 for c in pending}
            for k in [k for k in cache if k not in keep and k != clip.mp4]:
                del cache[k]
        frames, audio = cache[clip.mp4]
        write_caption(caption_file, clip.caption(args.overlay_text or "", args.prompt_chars))
        LOG.info("on air: %s (%d frames, %.2f s)", clip.label, len(frames), len(frames) / args.fps)
        for i, rgb in enumerate(frames):
            a0, a1 = round(i * samples_per_frame) * 2, round((i + 1) * samples_per_frame) * 2
            chunk = audio[a0:a1]
            if chunk.size < a1 - a0:
                chunk = np.concatenate([chunk, np.zeros(a1 - a0 - chunk.size, "<i2")])
            if done() or not send(rgb, chunk.tobytes()):
                break
            if args.interrupt and i % args.fps == 0 and time.monotonic() - last_scan >= args.scan_seconds:
                last_scan = time.monotonic()
                fresh = watcher.scan()
                if fresh:
                    pending.extend(fresh)
                    LOG.info("new clip finished: %s (interrupting)", fresh[-1].mp4)
                    break

    rc = encoder.close()
    LOG.info("stopped after %d frames on the last encoder (rc=%s)", n, rc)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    env_rtmp = os.environ.get("H3_STREAM_RTMP_URL", "").split()
    p.add_argument("clips", nargs="*", help="explicit clip.mp4 paths (also looped)")
    p.add_argument("--watch-dir", action="append", default=[], help="directory to watch (repeatable)")
    p.add_argument("--depth", type=int, default=3, help="max directory depth of receipt.json under a watch dir")
    p.add_argument("--rtmp-url", action="append", default=[], dest="rtmp_urls",
                   help="RTMP ingest URL incl. key (repeatable; env H3_STREAM_RTMP_URL)")
    p.add_argument("--whip-url", default=os.environ.get("H3_STREAM_WHIP_URL"), help="WHIP endpoint (env H3_STREAM_WHIP_URL)")
    p.add_argument("--whip-token", default=os.environ.get("H3_STREAM_WHIP_TOKEN"), help="WHIP bearer token, if any")
    p.add_argument("--test-sink", help="local file (.flv/.mkv/.ts) or local rtmp:// listener, for a keyless dry run")
    p.add_argument("--dry-run", action="store_true", help="print the ffmpeg command and the clips, then exit")
    p.add_argument("--show-secrets", action="store_true", help="with --dry-run, do not redact stream keys")
    p.add_argument("--keep-last", type=int, default=4, help="loop the most recent N clips (default 4)")
    p.add_argument("--interrupt", action="store_true", help="cut to a new clip at once instead of after the current one")
    p.add_argument("--overlay-text", default=DEFAULT_CAPTION, help="caption line under the clip name ('' = name only)")
    p.add_argument("--no-overlay", action="store_true", help="no caption at all")
    p.add_argument("--prompt-chars", type=int, default=0, help="also show the first N chars of the prompt (0 = off)")
    p.add_argument("--font", default=DEFAULT_FONT)
    p.add_argument("--font-size", type=int, default=16)
    p.add_argument("--size", default="auto", help="WxH output; auto = newest clip's size (exact pixels)")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--keyint-seconds", type=float, default=2.0)
    p.add_argument("--video-kbps", type=int, default=2500)
    p.add_argument("--audio-kbps", type=int, default=128)
    p.add_argument("--preset", default="veryfast")
    p.add_argument("--profile", default="baseline", help="x264 profile (baseline suits WebRTC and Twitch)")
    p.add_argument("--level", default=None, help="H.264 level, e.g. 3.1 for meshcast's 42e01f")
    p.add_argument("--duration", type=float, default=0, help="stop after N seconds (0 = forever)")
    p.add_argument("--scan-seconds", type=float, default=2.0)
    p.add_argument("--restart-delay", type=float, default=5.0)
    p.add_argument("--stall-seconds", type=float, default=30.0, help="restart the encoder if it accepts no input this long")
    p.add_argument("--no-verify", action="store_true", help="skip the clip.mp4 digest check against the receipt")
    p.add_argument("--state-dir", default=os.environ.get("XDG_RUNTIME_DIR", "/tmp"), help="where the caption file lives")
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.add_argument("--ffmpeg-loglevel", default="warning")
    args = p.parse_args(argv)
    args.rtmp_urls = args.rtmp_urls or env_rtmp
    if args.no_overlay:
        args.overlay_text = None
    if not args.watch_dir and not args.clips:
        p.error("give --watch-dir and/or clip paths")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stderr)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
