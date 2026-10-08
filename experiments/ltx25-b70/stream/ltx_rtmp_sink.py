#!/usr/bin/env python3
"""ltx_rtmp_sink.py - turn a growing, ordered list of short MP4 clips into ONE
continuous 24 fps live stream (RTMP or a local FLV file).

Design (CPU only, stdlib + PyAV + one ffmpeg subprocess):

  manifest.jsonl --(Loader thread: tail + decode ahead)--> decoded clip deque
        --(main loop: real-time pacing, 1 frame per tick)--> FfmpegOutput
        FfmpegOutput: video rgb24 -> ffmpeg stdin, audio s16le stereo 48 kHz
                      -> named pipe; ffmpeg encodes x264/AAC and pushes FLV.

The timeline is built by construction: every tick writes exactly one video
frame and exactly 2000 audio samples (48000/24), so audio and video can never
drift, including through holds (last frame + silence). Nothing is ever looped,
replayed or skipped because of lag; clips play strictly in manifest order.
"""
import argparse, datetime as dt, fcntl, json, os, queue, re, shutil, signal
import subprocess, sys, tempfile, threading, time, collections
from concurrent.futures import ThreadPoolExecutor
import av

FPS = 24
SR = 48000
SPF = SR // FPS                 # audio samples per video frame (2000)
ABYTES = SPF * 4                # s16 stereo bytes per frame
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def log(msg):
    ts = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    print(f"[sink {ts}] {msg}", file=sys.stderr, flush=True)


def atomic_write(path, text):
    """Write via tmp + rename so readers (ffmpeg drawtext, humans) never see a torn file."""
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def parse_utc(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class Clip:
    """A fully decoded clip: list of rgb24 frames at output size + s16le audio bytes."""
    def __init__(self, entry, frames, audio):
        self.entry, self.frames, self.audio = entry, frames, audio
        self.seq = int(entry["seq"])


def decode_clip(entry, W, H):
    """Decode one clip with PyAV: scale (lanczos) + letterbox video to WxH rgb24,
    resample audio to s16 stereo 48 kHz and pad/trim it to exactly len(frames)*SPF."""
    with av.open(entry["path"]) as c:
        vs = c.streams.video[0]
        rate = float(vs.average_rate or FPS)
        raw = []                             # (pts seconds, rgb bytes)
        sw = sh = None
        for fr in c.decode(vs):
            if sw is None:                   # fit inside WxH keeping aspect, even dims
                s = min(W / fr.width, H / fr.height)
                sw = min(W, max(2, int(round(fr.width * s / 2)) * 2))
                sh = min(H, max(2, int(round(fr.height * s / 2)) * 2))
            f2 = fr.reformat(width=sw, height=sh, format="rgb24", interpolation="LANCZOS")
            pl = f2.planes[0]
            buf, ls, rb = bytes(pl), pl.line_size, sw * 3
            if ls != rb:                     # strip swscale line padding
                buf = b"".join(buf[i * ls:i * ls + rb] for i in range(sh))
            if (sw, sh) != (W, H):           # letterbox / pillarbox with black
                lx = ((W - sw) // 2) * 3
                rx = W * 3 - rb - lx
                row_l, row_r = b"\0" * lx, b"\0" * rx
                top = (H - sh) // 2
                buf = (b"\0" * (W * 3 * top)
                       + b"".join(row_l + buf[i * rb:(i + 1) * rb] + row_r for i in range(sh))
                       + b"\0" * (W * 3 * (H - sh - top)))
            t = float(fr.pts * vs.time_base) if fr.pts is not None else len(raw) / rate
            raw.append((t, buf))
    if not raw:
        raise ValueError("no video frames")
    if abs(rate - FPS) < 0.01:
        frames = [b for _, b in raw]
    else:                                    # retime to 24 fps: latest frame with pts <= t
        t0, n = raw[0][0], int(round(len(raw) / rate * FPS))
        frames, j = [], 0
        for k in range(max(1, n)):
            while j + 1 < len(raw) and raw[j + 1][0] - t0 <= k / FPS + 1e-6:
                j += 1
            frames.append(raw[j][1])
    audio = bytearray()
    try:
        with av.open(entry["path"]) as c:
            if c.streams.audio:
                rs = av.AudioResampler(format="s16", layout="stereo", rate=SR)
                for fr in c.decode(c.streams.audio[0]):
                    for o in rs.resample(fr):
                        audio += bytes(o.planes[0])[:o.samples * 4]
                for o in rs.resample(None):
                    audio += bytes(o.planes[0])[:o.samples * 4]
    except Exception as e:                   # bad audio never blocks the video
        log(f"seq {entry.get('seq')}: audio decode failed ({e}); using silence")
        audio = bytearray()
    need = len(frames) * ABYTES
    audio = bytes(audio[:need]) + b"\0" * max(0, need - len(audio))
    return Clip(entry, frames, audio)


class Loader(threading.Thread):
    """Tails the JSONL manifest (0.2 s poll, partial-line safe) and decodes up to
    a few clips in advance so clip boundaries never stall the pacing loop."""
    def __init__(self, manifest, after_seq, W, H, workers=2):
        super().__init__(daemon=True)
        self.manifest, self.last_seq, self.W, self.H = manifest, after_seq, W, H
        self.workers, self.ahead = workers, workers + 1
        self.clip_secs = 25 / FPS            # updated with the last played clip length
        self.pending = collections.deque()   # manifest entries not yet submitted
        self.ready = collections.deque()     # (entry, Future[Clip]) in manifest order
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.offset, self.partial = 0, b""

    def poll_manifest(self):
        try:
            with open(self.manifest, "rb") as f:
                if os.fstat(f.fileno()).st_size < self.offset:
                    log("manifest shrank; re-reading from start (seqs already played are ignored)")
                    self.offset, self.partial = 0, b""
                f.seek(self.offset)
                data = f.read()
                self.offset += len(data)
        except FileNotFoundError:
            return
        data = self.partial + data
        lines = data.split(b"\n")
        self.partial = lines.pop()           # incomplete last line (no newline yet)
        for ln in lines:
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
                seq = int(e["seq"]); e["path"]
            except Exception as ex:
                log(f"manifest: bad line skipped ({ex}): {ln[:120]!r}")
                continue
            if seq <= self.last_seq:
                continue                     # already played / queued (resume, duplicates)
            self.last_seq = seq
            with self.lock:
                self.pending.append(e)

    def _decode(self, e):
        err = None
        for attempt in range(10):            # file may still be settling on disk
            try:
                return decode_clip(e, self.W, self.H)
            except Exception as ex:
                err = ex
                time.sleep(0.2)
        log(f"seq {e['seq']}: cannot decode {e['path']} ({err}); skipped as unplayable")
        return None

    def run(self):
        # PyAV releases the GIL in decode/swscale, so a small thread pool scales;
        # futures stay in manifest order, so playback order is never changed.
        with ThreadPoolExecutor(self.workers) as pool:
            while not self.stop.is_set():
                self.poll_manifest()
                with self.lock:
                    while self.pending and len(self.ready) < self.ahead:
                        e = self.pending.popleft()
                        self.ready.append((e, pool.submit(self._decode, e)))
                self.stop.wait(0.2)

    def take(self):
        """Next decoded clip in order, or None if it is not ready yet (never blocks)."""
        while True:
            with self.lock:
                if not self.ready or not self.ready[0][1].done():
                    return None
                _, fut = self.ready.popleft()
            clip = fut.result()
            if clip is not None:
                return clip                  # (undecodable entries are dropped, logged)

    def buffered(self):
        """(clip count, approx seconds) waiting behind the current clip."""
        with self.lock:
            n = len(self.ready) + len(self.pending)
        return n, n * self.clip_secs


def esc(v):
    """Escape a value for an ffmpeg filtergraph option."""
    return v.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


class FfmpegOutput:
    """One ffmpeg encoder process plus two writer threads (video stdin, audio FIFO)."""
    def __init__(self, a, workdir, target, W, H):
        self.fifo = os.path.join(workdir, "audio.s16le")
        if not os.path.exists(self.fifo):
            os.mkfifo(self.fifo)
        cmd = ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostats", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-framerate", str(FPS),
               "-thread_queue_size", "64", "-i", "pipe:0",
               "-f", "s16le", "-ar", str(SR), "-ch_layout", "stereo", "-thread_queue_size", "512",
               "-i", self.fifo]
        if a.overlay_file:
            fs = max(12, H // 48)
            font = f"fontfile='{esc(a.font)}':" if a.font else ""
            cmd += ["-vf", (f"drawtext={font}textfile='{esc(a.overlay_file)}'"
                            f":reload=1:expansion=none:fontsize={fs}:fontcolor=white"
                            f":line_spacing={fs // 4}:box=1:boxcolor=black@0.55:boxborderw={fs // 3}"
                            f":x=(w-text_w)/2:y=h-text_h-{fs}")]
        cmd += ["-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                "-b:v", "2500k", "-maxrate", "2500k", "-bufsize", "5000k",
                "-g", "48", "-keyint_min", "48", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", str(SR), "-ac", "2",
                "-f", "flv"]
        if a.rtmp:                           # live: no seekable header to rewrite at the end
            cmd += ["-flvflags", "no_duration_filesize"]
        cmd.append(target)
        log(f"ffmpeg start -> {target}")
        # own session: a terminal Ctrl-C reaches only the sink, which then shuts ffmpeg down cleanly
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, start_new_session=True)
        self.vq, self.aq = queue.Queue(maxsize=48), queue.Queue(maxsize=48)
        self.broken = threading.Event()
        self.threads = [threading.Thread(target=self._vwriter, daemon=True),
                        threading.Thread(target=self._awriter, daemon=True)]
        for t in self.threads:
            t.start()

    def alive(self):
        return self.proc.poll() is None and not self.broken.is_set()

    def _pump(self, q, fd):
        try:
            while True:
                item = q.get()
                if item is None:
                    break
                mv = memoryview(item)
                while mv:
                    mv = mv[os.write(fd, mv):]
        except OSError:                      # BrokenPipe: ffmpeg died / disconnected
            self.broken.set()

    def _vwriter(self):
        self._pump(self.vq, self.proc.stdin.fileno())
        try:
            self.proc.stdin.close()
        except OSError:
            pass

    def _awriter(self):
        fd = None
        while fd is None and self.proc.poll() is None:   # wait for ffmpeg to open the FIFO
            try:
                fd = os.open(self.fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                time.sleep(0.05)
        if fd is None:
            self.broken.set()
            return
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl & ~os.O_NONBLOCK)
        self._pump(self.aq, fd)
        os.close(fd)

    def write(self, vframe, aframe):
        """Queue one frame + its audio; blocks (back-pressure) while ffmpeg is slow."""
        for q, item in ((self.vq, vframe), (self.aq, aframe)):
            while self.alive():
                try:
                    q.put(item, timeout=0.5)
                    break
                except queue.Full:
                    pass

    def close(self, timeout=20):
        """Deliver an end sentinel to BOTH writers even if ffmpeg is dead (a writer
        left blocked in q.get() would keep the FIFO open, so the next ffmpeg would
        never see audio EOF), then reap ffmpeg; never raises."""
        for q in (self.vq, self.aq):
            while True:
                try:
                    q.put_nowait(None)
                    break
                except queue.Full:
                    if self.alive():
                        time.sleep(0.05)
                    else:
                        try:
                            q.get_nowait()   # ffmpeg gone: drop unsent frames
                        except queue.Empty:
                            pass
        for t in self.threads:
            t.join(timeout)
        try:
            return self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            log("ffmpeg did not exit; terminating it")
            self.proc.terminate()
            try:
                return self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                return self.proc.wait()


def wrap(text, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split(" "):
            if line and len(line) + 1 + len(w) > width:
                out.append(line); line = w
            else:
                line = f"{line} {w}" if line else w
        out.append(line)
    return "\n".join(out)


class Sink:
    def __init__(self, a):
        self.a = a
        self.W, self.H = (int(x) for x in a.size.lower().split("x"))
        self.workdir = a.workdir or tempfile.mkdtemp(prefix="ltx-sink-")
        os.makedirs(self.workdir, exist_ok=True)
        a.overlay_file = None if a.no_overlay else os.path.join(self.workdir, "overlay.txt")
        self.wrapw = max(20, int(self.W / (0.55 * max(12, self.H // 48))))
        state = {}
        if a.state and os.path.exists(a.state):
            with open(a.state) as f:
                state = json.load(f)
        self.last_played = state.get("last_played_seq", -1)
        if a.start_seq is not None:
            self.last_played = a.start_seq - 1
        log(f"resuming after seq {self.last_played} (workdir {self.workdir})")
        self.loader = Loader(a.manifest, self.last_played, self.W, self.H, a.decode_threads)
        self.stop_after_clip = threading.Event()   # 1st signal: finish clip, then stop
        self.stop_now = threading.Event()          # 2nd signal: stop at next frame
        self.st = dict(played_clips=0, holds=0, total_hold_seconds=0.0, current_lag_seconds=None,
                       ffmpeg_alive=False, ffmpeg_restarts=0, last_played_seq=self.last_played,
                       frames_emitted=0, slips=0, last_hold_seconds=0.0)
        self.n_out = 0                              # ffmpeg instance count (file suffixes)
        self.deletions = []                         # (due wall time, dir)
        self.last_frame = b"\0" * (self.W * self.H * 3)
        self.silence = b"\0" * ABYTES
        self.next_stats = 0.0
        self.over_ahead = False
        self.out = None

    # ---------- helpers ----------
    def target(self):
        if self.a.rtmp:
            return self.a.rtmp
        if self.n_out == 0:
            return self.a.out
        root, ext = os.path.splitext(self.a.out)     # never overwrite after a reconnect
        return f"{root}.r{self.n_out}{ext}"

    def set_overlay(self, dyn):
        if self.a.overlay_file:
            atomic_write(self.a.overlay_file, wrap(f"{self.a.title}\n{dyn}" if self.a.title else dyn,
                                                   self.wrapw))

    def save_state(self):
        if self.a.state:
            atomic_write(self.a.state, json.dumps({"last_played_seq": self.last_played,
                                                   "updated_utc": time.time()}) + "\n")

    def write_stats(self, force=False):
        now = time.monotonic()
        if not self.a.stats or (now < self.next_stats and not force):
            return
        self.next_stats = now + 5.0
        n, secs = self.loader.buffered()
        s = dict(self.st, buffered_clips=n, buffered_seconds=round(secs, 2),
                 stream_seconds=round(self.st["frames_emitted"] / FPS, 3),
                 total_hold_seconds=round(self.st["total_hold_seconds"], 3),
                 ffmpeg_alive=bool(self.out and self.out.alive()),
                 updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        atomic_write(self.a.stats, json.dumps(s, indent=1) + "\n")

    def dispose(self):
        now = time.time()
        while self.deletions and self.deletions[0][0] <= now:
            _, d = self.deletions.pop(0)
            try:
                shutil.rmtree(d)
                log(f"disposed played clip dir {d}")
            except OSError as e:
                log(f"dispose failed for {d}: {e}")

    def schedule_dispose(self, clip):
        a = self.a
        if a.delete_played_after_seconds is None or not a.disposable_dir_regex:
            return
        d = os.path.dirname(os.path.abspath(clip.entry["path"]))
        if re.fullmatch(a.disposable_dir_regex, os.path.basename(d)):
            self.deletions.append((time.time() + a.delete_played_after_seconds, d))

    # ---------- the paced emit ----------
    def emit(self, vframe, aframe):
        """Write one frame at its wall-clock slot; reconnect ffmpeg if it died."""
        if not self.out.alive():
            rc = self.out.proc.poll()
            log(f"ffmpeg exited (rc={rc}); reconnecting in 5 s from current position")
            self.out.close(timeout=2)
            self.st["ffmpeg_restarts"] += 1
            if self.stop_now.wait(5.0):
                return
            self.n_out += 1
            self.out = FfmpegOutput(self.a, self.workdir, self.target(), self.W, self.H)
            self.t0, self.k = time.monotonic(), 0
        due = self.t0 + self.k / (FPS * self.a.speed)
        now = time.monotonic()
        if due > now:
            time.sleep(due - now)
        elif now - due > 2.0 / (FPS * self.a.speed):  # blocked: re-anchor, never burst ahead
            self.t0, self.k = now, 0
            self.st["slips"] += 1
        self.k += 1
        self.out.write(vframe, aframe)
        self.st["frames_emitted"] += 1
        self.write_stats()

    def hold_until_clip(self):
        """Starvation: hold the last frame + silence until a clip is ready."""
        clip = self.loader.take()
        if clip or self.stop_now.is_set():
            return clip
        held, nxt_txt = 0, 0
        log(f"HOLD start after seq {self.last_played} (generator behind)")
        self.st["holds"] += 1
        while not self.stop_now.is_set() and not self.stop_after_clip.is_set():
            if held >= nxt_txt:                  # refresh overlay ~2x per stream second
                self.set_overlay(f"buffering… generator behind by {held / FPS:.1f} s")
                nxt_txt = held + FPS // 2
            self.emit(self.last_frame, self.silence)
            self.dispose()
            held += 1
            self.st["total_hold_seconds"] += 1.0 / FPS
            clip = self.loader.take()
            if clip:
                break
        self.st["last_hold_seconds"] = round(held / FPS, 3)
        log(f"HOLD end after {held / FPS:.2f} s")
        return clip

    def run(self):
        self.loader.start()
        self.set_overlay("starting…")
        self.out = FfmpegOutput(self.a, self.workdir, self.target(), self.W, self.H)
        self.t0, self.k = time.monotonic(), 0
        try:
            while not self.stop_after_clip.is_set() and not self.stop_now.is_set():
                self.dispose()
                clip = self.hold_until_clip()
                if clip is None:
                    break
                e = clip.entry
                gen = parse_utc(e.get("generated_utc", ""))
                lag = (time.time() - gen) if gen else None
                self.st["current_lag_seconds"] = None if lag is None else round(lag, 1)
                self.loader.clip_secs = len(clip.frames) / FPS
                n, secs = self.loader.buffered()
                if secs > self.a.max_ahead_seconds and not self.over_ahead:
                    log(f"buffer {secs:.0f} s exceeds --max-ahead-seconds; playing in order anyway")
                self.over_ahead = secs > self.a.max_ahead_seconds
                hms = time.strftime("%H:%M:%S", time.gmtime(gen)) if gen else "?"
                lag_s = f"{lag:.1f}" if lag is not None else "?"
                self.set_overlay(f"clip {clip.seq} · {e.get('label', '')} · generated {hms} UTC"
                                 f" · stream lag {lag_s} s · buffered {n} clips")
                log(f"play seq {clip.seq} frames={len(clip.frames)} lag={lag_s}s buffered={n} "
                    f"path={e['path']}")
                for i, fr in enumerate(clip.frames):
                    if self.stop_now.is_set():
                        break
                    self.emit(fr, clip.audio[i * ABYTES:(i + 1) * ABYTES])
                    self.last_frame = fr
                else:                                    # clip fully played
                    self.last_played = clip.seq
                    self.st["played_clips"] += 1
                    self.st["last_played_seq"] = clip.seq
                    self.save_state()
                    self.schedule_dispose(clip)
        finally:
            log("shutting down: flushing pipes and waiting for ffmpeg")
            self.loader.stop.set()
            self.save_state()
            rc = self.out.close()
            log(f"ffmpeg exited rc={rc}; last_played_seq={self.last_played}")
            self.save_state()
            self.st["ffmpeg_alive"] = False
            self.write_stats(force=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--manifest", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--rtmp", help="rtmp://host/app/streamkey")
    g.add_argument("--out", help="local FLV file (testing)")
    p.add_argument("--state", help="JSON resume file (last played seq)")
    p.add_argument("--stats", help="JSON stats file, rewritten every 5 s")
    p.add_argument("--size", default="768x768")
    p.add_argument("--title", default="")
    p.add_argument("--no-overlay", action="store_true")
    p.add_argument("--font", default=FONT if os.path.exists(FONT) else "")
    p.add_argument("--start-seq", type=int, help="play seqs >= N (overrides --state)")
    p.add_argument("--max-ahead-seconds", type=float, default=600.0,
                   help="warn when buffer exceeds this; never skips")
    p.add_argument("--delete-played-after-seconds", type=float)
    p.add_argument("--disposable-dir-regex", default=None,
                   help="only parent dirs whose basename fully matches are deleted")
    p.add_argument("--workdir", help="dir for the audio FIFO and overlay text (default: mkdtemp)")
    p.add_argument("--decode-threads", type=int, default=2)
    p.add_argument("--speed", type=float, default=1.0, help="TEST ONLY: pace faster than real time")
    a = p.parse_args()
    if not a.font:
        log("no DejaVu font found; using ffmpeg/fontconfig default")
    sink = Sink(a)

    def on_signal(signum, _):
        if sink.stop_after_clip.is_set():
            sink.stop_now.set()
            log(f"signal {signum} again: stopping now")
        else:
            sink.stop_after_clip.set()
            log(f"signal {signum}: finishing current clip, then clean shutdown")
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    sink.run()


if __name__ == "__main__":
    main()
