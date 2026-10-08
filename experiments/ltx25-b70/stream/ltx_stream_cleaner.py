#!/usr/bin/env python3
"""Disk cleaner for the live s97 stream01 LTX run directory (CPU only, stdlib only).

Deletes per-clip receipt files from the run directory once the sink has played
the clip (with a margin) and the file is old enough. It never touches output/
(mp4 previews are deleted by the sink; validation summaries are kept forever),
never deletes directories, never follows symlinks, and never deletes a name
that it cannot map to a played stream seq through the manifest.

Naming (learned from the live directory on 2026-10-07):
  <family>-s97-twowayw2b2p1dxpu2-stream01-RRRRRRR.json   R = request number
  pipeline-done-<stage>-IIIIIIII.json                     I = clip index
The manifest maps both to the stream seq: request R = seq + 5 on this run
(requests 0..4 are warmups that never reach the manifest) and I = 50001000 + seq.
The cleaner does not assume either offset; it uses the manifest lines only.

  python3 -B ltx_stream_cleaner.py --once            # dry run (default)
  python3 -B ltx_stream_cleaner.py --apply           # live, every 300 s
"""
import argparse, json, os, re, signal, stat, sys, time
from datetime import datetime, timezone

RUN_NAME = 'encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01'
PREFIX = 's97-twowayw2b2p1dxpu2-stream01'
RUN_DIR = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/' + RUN_NAME
STREAM_DIR = '/home/steve/ltx-stream/s97-stream01'

# Exact per-clip receipt families seen in the run directory (11 request-named + 3 index-named).
REQ_FAMILIES = frozenset([
    'concurrent-cfg', 'fusion', 'graph-capture', 'pipeline', 'pipeline-decode',
    'pipeline-sampler', 'pipeline-save', 'resident-fastpath', 'text-encoder-graph',
    'upsampler-graph', 'vae-graph',
])
DONE_STAGES = frozenset(['sample', 'decode', 'save'])
INDEX_MIN, INDEX_MAX = 50001000, 99999999

RE_REQ = re.compile(r'^(?P<fam>[a-z0-9-]+)-' + re.escape(PREFIX) + r'-(?P<num>[0-9]{7})\.json$')
RE_DONE = re.compile(r'^pipeline-done-(?P<fam>[a-z0-9-]+)-(?P<num>[0-9]{8})\.json$')
# Anything carrying the stream's request number or a stream index that is not an exact match above.
RE_TOUCHES_STREAM = re.compile(re.escape(PREFIX) + r'-[0-9]{7}|^pipeline-done-')
RE_MANIFEST_PATH = re.compile(r'/' + re.escape(PREFIX) + r'-(?P<num>[0-9]{7})/[^/]+$')

GIB = 1 << 30


def log(msg):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'{ts} {msg}', flush=True)


def free_bytes(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


class Manifest:
    """Incremental reader of manifest.jsonl: request number -> seq and clip index -> seq."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.ino = None
        self.req_seq, self.idx_seq = {}, {}
        self.ambiguous_req, self.ambiguous_idx = set(), set()
        self.bad_lines = 0
        self.max_seq = -1

    def _reset(self):
        self.__init__(self.path)

    def _add(self, table, bad, key, seq):
        old = table.get(key)
        if old is not None and old != seq:
            bad.add(key)
        table[key] = seq

    def refresh(self):
        st = os.stat(self.path)
        if self.ino is not None and (st.st_ino != self.ino or st.st_size < self.offset):
            log(f'manifest replaced or truncated; re-reading {self.path}')
            self._reset()
        self.ino = st.st_ino
        with open(self.path, 'rb') as f:
            f.seek(self.offset)
            data = f.read()
        end = data.rfind(b'\n')
        if end < 0:
            return
        for raw in data[:end].split(b'\n'):
            if not raw.strip():
                continue
            try:
                r = json.loads(raw)
                seq, idx, path = r['seq'], r['index'], r['path']
                if not (isinstance(seq, int) and isinstance(idx, int) and seq >= 0):
                    raise ValueError('types')
                m = RE_MANIFEST_PATH.search(path)
                if not m:
                    raise ValueError('path')
            except Exception:
                self.bad_lines += 1
                continue
            self._add(self.req_seq, self.ambiguous_req, int(m.group('num')), seq)
            self._add(self.idx_seq, self.ambiguous_idx, idx, seq)
            self.max_seq = max(self.max_seq, seq)
        self.offset += end + 1


def read_last_played(path):
    with open(path) as f:
        v = json.load(f)['last_played_seq']
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ValueError(f'bad last_played_seq {v!r}')
    return v


def check_run_dir(run_dir):
    a = os.path.abspath(run_dir)
    if os.path.realpath(a) != a:
        raise SystemExit(f'refusing: run dir path contains a symlink: {a}')
    if any(p.startswith('prepared-') for p in a.split(os.sep)):
        raise SystemExit(f'refusing: run dir is under a prepared-* packet: {a}')
    if os.path.basename(a) != RUN_NAME:
        raise SystemExit(f'refusing: run dir basename must be {RUN_NAME}: {a}')
    if not os.path.isdir(a):
        raise SystemExit(f'refusing: run dir missing: {a}')
    return a


def classify(name, manifest):
    """Return (kind, family, seq). kind in: stream, unknown, other, unmapped."""
    m = RE_REQ.match(name)
    if m:
        fam = m.group('fam')
        if fam not in REQ_FAMILIES:
            return 'unknown', fam, None
        num = int(m.group('num'))
        if num in manifest.ambiguous_req or num not in manifest.req_seq:
            return 'unmapped', fam, None
        return 'stream', fam, manifest.req_seq[num]
    m = RE_DONE.match(name)
    if m:
        fam = 'pipeline-done-' + m.group('fam')
        num = int(m.group('num'))
        if not (INDEX_MIN <= num <= INDEX_MAX):
            return 'other', fam, None          # e.g. 50000000..50000412 from earlier runs
        if m.group('fam') not in DONE_STAGES:
            return 'unknown', fam, None
        if num in manifest.ambiguous_idx or num not in manifest.idx_seq:
            return 'unmapped', fam, None
        return 'stream', fam, manifest.idx_seq[num]
    if RE_TOUCHES_STREAM.search(name) and re.search(r'[0-9]{7}', name):
        return 'unknown', re.sub(r'[0-9]{7,8}', 'N', name), None
    return 'other', None, None


class Cleaner:
    def __init__(self, args):
        self.a = args
        self.run_dir = check_run_dir(args.run_dir)
        self.manifest = Manifest(args.manifest)
        self.unknown_logged = set()
        self.cycle = 0
        self.total_files = 0
        self.total_bytes = 0

    def run_cycle(self):
        a = self.a
        self.cycle += 1
        apply = a.apply
        now = time.time()
        free_before = free_bytes(self.run_dir)
        stats = {'cycle': self.cycle, 'utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 'mode': 'apply' if apply else 'dry-run', 'run_dir': self.run_dir,
                 'free_before_bytes': free_before}
        try:
            last_played = read_last_played(a.sink_stats)
            self.manifest.refresh()
        except Exception as e:
            log(f'SKIP cycle {self.cycle}: cannot read sink stats/manifest: {e!r}; nothing deleted')
            stats.update(status='skipped', error=repr(e), free_after_bytes=free_before)
            self._finish(stats, free_before, free_before)
            return stats
        threshold = last_played - a.played_margin
        cutoff = now - a.min_age_seconds
        counts = dict(deleted=0, too_young=0, not_played=0, sample=0, unmapped=0, unknown=0,
                      not_regular=0, errors=0)
        by_family = {}
        freed = 0
        deleted_seqs = []
        present_count = {}
        removed_seqs_files = {}
        dfd = os.open(self.run_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with os.scandir(dfd) as it:
                names = [e.name for e in it]
            plan = []
            for name in names:
                kind, fam, seq = classify(name, self.manifest)
                if kind == 'other':
                    continue
                if kind == 'unknown':
                    counts['unknown'] += 1
                    key = re.sub(r'[0-9]{7,8}', 'N', name)
                    if key not in self.unknown_logged:
                        self.unknown_logged.add(key)
                        log(f'UNKNOWN family, skipped (logged once): {key}')
                    continue
                if kind == 'unmapped':
                    counts['unmapped'] += 1
                    continue
                try:
                    st = os.lstat(name, dir_fd=dfd)
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    counts['not_regular'] += 1
                    continue
                present_count[seq] = present_count.get(seq, 0) + 1
                if seq > threshold:
                    counts['not_played'] += 1
                elif a.keep_every > 0 and seq % a.keep_every == 0:
                    counts['sample'] += 1
                elif st.st_mtime >= cutoff:
                    counts['too_young'] += 1
                else:
                    plan.append((seq, name, fam, st))
            plan.sort()
            for seq, name, fam, st in plan:
                try:
                    st2 = os.lstat(name, dir_fd=dfd)
                    if (not stat.S_ISREG(st2.st_mode) or st2.st_ino != st.st_ino
                            or st2.st_mtime >= cutoff):
                        counts['not_regular'] += 1
                        continue
                    if apply:
                        os.unlink(name, dir_fd=dfd)
                    else:
                        print(f'WOULD-DELETE seq={seq} {st2.st_size} {name}')
                except FileNotFoundError:
                    continue
                except OSError as e:
                    counts['errors'] += 1
                    log(f'ERROR deleting {name}: {e!r}')
                    continue
                counts['deleted'] += 1
                freed += st2.st_size
                by_family[fam] = by_family.get(fam, 0) + 1
                deleted_seqs.append(seq)
                removed_seqs_files[seq] = removed_seqs_files.get(seq, 0) + 1
        finally:
            os.close(dfd)
        # A seq is kept while any of its files remains (projected for a dry run).
        remaining = {q for q, n in present_count.items() if n > removed_seqs_files.get(q, 0)}
        nonsample = [s for s in remaining if not (a.keep_every > 0 and s % a.keep_every == 0)]
        free_after = free_bytes(self.run_dir)
        self.total_files += counts['deleted'] if apply else 0
        self.total_bytes += freed if apply else 0
        stats.update(status='ok', last_played_seq=last_played, delete_through_seq=threshold,
                     manifest_max_seq=self.manifest.max_seq, manifest_bad_lines=self.manifest.bad_lines,
                     files=counts['deleted'], bytes=freed, by_family=dict(sorted(by_family.items())),
                     skipped=counts, oldest_deleted_seq=min(deleted_seqs) if deleted_seqs else None,
                     newest_deleted_seq=max(deleted_seqs) if deleted_seqs else None,
                     oldest_kept_seq=min(nonsample) if nonsample else None,
                     samples_kept=sorted(s for s in remaining if s not in nonsample),
                     unknown_families=sorted(self.unknown_logged),
                     total_deleted_files=self.total_files, total_freed_bytes=self.total_bytes,
                     free_after_bytes=free_after)
        verb = 'deleted' if apply else 'would-delete'
        log(f'cycle {self.cycle} [{stats["mode"]}] {verb} {counts["deleted"]} files {freed} bytes '
            f'({freed / 1e6:.1f} MB) seqs {stats["oldest_deleted_seq"]}..{stats["newest_deleted_seq"]} '
            f'free {free_before / GIB:.2f} -> {free_after / GIB:.2f} GiB '
            f'last_played={last_played} through={threshold} oldest_kept_seq={stats["oldest_kept_seq"]} '
            f'skipped={counts}')
        self._finish(stats, free_before, free_after)
        return stats

    def _finish(self, stats, free_before, free_after):
        a = self.a
        alarm = free_after < a.alarm_gib * GIB
        stats['alarm'] = alarm
        if alarm:
            log(f'ALARM free space {free_after / GIB:.2f} GiB is below {a.alarm_gib} GiB '
                f'(lab reserve 50 GiB) on {self.run_dir}')
        if a.stats_out:
            tmp = a.stats_out + '.tmp'
            try:
                with open(tmp, 'w') as f:
                    json.dump(stats, f, indent=1)
                    f.write('\n')
                os.replace(tmp, a.stats_out)
            except OSError as e:
                log(f'ERROR writing stats {a.stats_out}: {e!r}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run-dir', default=RUN_DIR)
    ap.add_argument('--sink-stats', default=STREAM_DIR + '/sink-stats.json')
    ap.add_argument('--manifest', default=STREAM_DIR + '/manifest.jsonl')
    ap.add_argument('--stats-out', default=STREAM_DIR + '/cleaner-stats.json')
    ap.add_argument('--interval', type=float, default=300)
    ap.add_argument('--played-margin', type=int, default=100)
    ap.add_argument('--min-age-seconds', type=float, default=3600)
    ap.add_argument('--keep-every', type=int, default=500)
    ap.add_argument('--alarm-gib', type=float, default=52)
    ap.add_argument('--once', action='store_true')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--apply', action='store_true', help='really delete (default is dry run)')
    g.add_argument('--dry-run', action='store_true', help='print what would be deleted (the default)')
    a = ap.parse_args(argv)
    if a.played_margin < 0 or a.min_age_seconds < 0 or a.interval <= 0:
        ap.error('margin/min-age must be >= 0 and interval > 0')
    c = Cleaner(a)
    log(f'start mode={"apply" if a.apply else "dry-run"} run_dir={c.run_dir} margin={a.played_margin} '
        f'min_age={a.min_age_seconds}s keep_every={a.keep_every} interval={a.interval}s alarm<{a.alarm_gib}GiB')
    stop = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.append(1))
    while True:
        try:
            c.run_cycle()
        except SystemExit:
            raise
        except Exception as e:
            log(f'ERROR cycle {c.cycle} failed: {e!r}')
        if a.once:
            return 0
        deadline = time.monotonic() + a.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
        if stop:
            log('stop signal; exiting')
            return 0


if __name__ == '__main__':
    sys.exit(main())
