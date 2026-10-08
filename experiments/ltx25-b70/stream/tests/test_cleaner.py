#!/usr/bin/env python3
"""Unit test of ltx_stream_cleaner.py on a fake run dir with the live naming (CPU only, stdlib only).

    python3 -B tests/test_cleaner.py
"""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEANER = HERE.parent / 'ltx_stream_cleaner.py'
RUN = 'encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01'
P = 's97-twowayw2b2p1dxpu2-stream01'
REQ_FAMS = ['concurrent-cfg', 'fusion', 'graph-capture', 'pipeline', 'pipeline-decode', 'pipeline-sampler',
            'pipeline-save', 'resident-fastpath', 'text-encoder-graph', 'upsampler-graph', 'vae-graph']
DONE = ['sample', 'decode', 'save']
OFFSET = 5            # live run: request number = seq + 5
OLD = time.time() - 7200
LAST_PLAYED = 700     # margin 100 -> seqs <= 600 are played enough


def clip_files(seq):
    r = seq + OFFSET
    return ([f'{f}-{P}-{r:07d}.json' for f in REQ_FAMS] +
            [f'pipeline-done-{s}-{50001000 + seq}.json' for s in DONE])


class CleanerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ltx-cleaner-test-'))
        self.root = self.tmp / 'bench'
        self.run = self.root / RUN
        self.run.mkdir(parents=True)
        self.stream = self.tmp / 'stream'
        self.stream.mkdir()
        self.seqs_old = list(range(0, 12)) + [500, 599, 600, 601, 650]
        self.young_seq = 20
        with open(self.stream / 'manifest.jsonl', 'w') as f:
            for seq in sorted(self.seqs_old + [self.young_seq]):
                f.write(json.dumps({'seq': seq, 'index': 50001000 + seq,
                                    'path': f'{self.root}/output/{P}-{seq + OFFSET:07d}/preview_00001_.mp4'}) + '\n')
            f.write('{"seq": 9999, "index": 5001')          # partial last line: must be ignored
        (self.stream / 'sink-stats.json').write_text(json.dumps({'last_played_seq': LAST_PLAYED}))
        for seq in self.seqs_old:
            for n in clip_files(seq):
                self.mk(n, OLD)
        for n in clip_files(self.young_seq):
            self.mk(n)                                          # mtime now: too young
        # Never-delete files, all old.
        self.keep_names = []
        for r in range(OFFSET):                                 # warmup requests 0..4 (not in manifest)
            for f in REQ_FAMS:
                self.keep(f'{f}-{P}-{r:07d}.json')
        for n in [f'pipeline-done-sample-{50000000 + 3}.json',  # earlier run, below index range
                  f'pipeline-done-save-{50000412}.json',
                  f'pipeline-done-foo-{50001003}.json',         # unknown stage, in range
                  f'newfamily-{P}-{3 + OFFSET:07d}.json',        # unknown family (logged once)
                  f'newfamily-{P}-{4 + OFFSET:07d}.json',
                  f'pipeline-{P}-{3 + OFFSET:07d}.json.tmp',      # unknown suffix
                  f'vae-graph-{P}-proofs-01.json', f'pipeline-{P}-cap0-00.json',
                  f'text-encoder-graph-{P}-wprobe.json',
                  'server-args.json', 'health-receipt.json', 'journal-before.txt',
                  f'pipeline-s97-otherstream02-{3 + OFFSET:07d}.json']:
            self.keep(n)
        # Symlink and directory carrying an eligible-looking name for played seq 7 / 8 (their real files removed).
        target = self.tmp / 'outside-target.json'
        target.write_text('x')
        os.utime(target, (OLD, OLD))
        sl = self.run / f'graph-capture-{P}-{7 + OFFSET:07d}.json'
        sl.unlink(); sl.symlink_to(target)
        os.utime(sl, (OLD, OLD), follow_symlinks=False)
        self.keep_names.append(sl.name)
        d = self.run / f'fusion-{P}-{8 + OFFSET:07d}.json'
        d.unlink(); d.mkdir(); (d / 'inner.json').write_text('x')
        os.utime(d, (OLD, OLD))
        self.keep_names.append(d.name)
        for sub in ['inductor-cache', 'temp', 'user', 'input']:
            (self.run / sub).mkdir()
        # Outputs next to the run dir: must be untouched.
        v = self.root / 'output' / 'validation' / f'{P}-{1 + OFFSET:07d}'
        v.mkdir(parents=True)
        (v / 'summary.json').write_text('{}')
        mp4 = self.root / 'output' / f'{P}-{1 + OFFSET:07d}'
        mp4.mkdir()
        (mp4 / 'preview_00001_.mp4').write_text('mp4')
        for p in [v / 'summary.json', mp4 / 'preview_00001_.mp4']:
            os.utime(p, (OLD, OLD))
        self.outputs = [v / 'summary.json', mp4 / 'preview_00001_.mp4']

    def mk(self, name, mtime=None):
        p = self.run / name
        p.write_text('{"x": 1}\n' * 10)
        if mtime is not None:
            os.utime(p, (mtime, mtime))
        return p

    def keep(self, name):
        self.mk(name, OLD)
        self.keep_names.append(name)

    def run_cleaner(self, *extra):
        cmd = [sys.executable, '-B', str(CLEANER), '--once', '--run-dir', str(self.run),
               '--sink-stats', str(self.stream / 'sink-stats.json'),
               '--manifest', str(self.stream / 'manifest.jsonl'),
               '--stats-out', str(self.stream / 'cleaner-stats.json'), *extra]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout, json.loads((self.stream / 'cleaner-stats.json').read_text())

    def expected_deleted(self):
        exp = set()
        for seq in self.seqs_old:
            if seq % 500 == 0 or seq > LAST_PLAYED - 100:
                continue
            exp.update(clip_files(seq))
        exp.discard(f'graph-capture-{P}-{7 + OFFSET:07d}.json')   # symlink
        exp.discard(f'fusion-{P}-{8 + OFFSET:07d}.json')          # directory
        return exp

    def test_dry_run_then_apply(self):
        before = set(os.listdir(self.run))
        exp = self.expected_deleted()
        self.assertEqual(len(exp), 13 * 14 - 2)  # seqs 1..11, 599, 600; minus symlink and dir
        out, st = self.run_cleaner('--dry-run')
        self.assertEqual(set(os.listdir(self.run)), before, 'dry run removed something')
        would = {l.split()[-1] for l in out.splitlines() if l.startswith('WOULD-DELETE')}
        self.assertEqual(would, exp)
        self.assertEqual(st['mode'], 'dry-run')
        self.assertEqual(st['files'], len(exp))

        out, st = self.run_cleaner('--apply')
        after = set(os.listdir(self.run))
        self.assertEqual(before - after, exp)
        self.assertEqual(after - before, set())
        for n in self.keep_names:
            self.assertTrue(os.path.lexists(self.run / n), n)
        self.assertTrue((self.run / f'graph-capture-{P}-{7 + OFFSET:07d}.json').is_symlink())
        self.assertTrue((self.tmp / 'outside-target.json').exists())
        self.assertTrue((self.run / f'fusion-{P}-{8 + OFFSET:07d}.json' / 'inner.json').exists())
        for p in self.outputs:
            self.assertTrue(p.exists(), p)
        for seq in [0, 500, 601, 650, self.young_seq]:
            for n in clip_files(seq):
                self.assertIn(n, after, n)
        self.assertEqual(st['mode'], 'apply')
        self.assertEqual(st['files'], len(exp))
        self.assertEqual(st['bytes'], len(exp) * len('{"x": 1}\n' * 10))
        self.assertEqual(st['oldest_deleted_seq'], 1)
        self.assertEqual(st['newest_deleted_seq'], 600)
        self.assertEqual(st['oldest_kept_seq'], self.young_seq)  # too-young seq 20; symlink/dir are not clip files
        self.assertEqual(st['samples_kept'], [0, 500])
        self.assertEqual(sorted(st['unknown_families']),
                         sorted([f'newfamily-{P}-N.json', f'pipeline-{P}-N.json.tmp', 'pipeline-done-foo-N.json']))
        self.assertEqual(out.count('UNKNOWN family'), 3)
        self.assertIn('free', out)
        # Second apply is a no-op.
        out, st = self.run_cleaner('--apply')
        self.assertEqual(st['files'], 0)
        self.assertEqual(set(os.listdir(self.run)), after)

    def test_bad_sink_stats_deletes_nothing(self):
        (self.stream / 'sink-stats.json').write_text('{"played_clips": 3}')
        before = set(os.listdir(self.run))
        out, st = self.run_cleaner('--apply')
        self.assertEqual(st['status'], 'skipped')
        self.assertEqual(set(os.listdir(self.run)), before)

    def test_alarm_line(self):
        out, st = self.run_cleaner('--dry-run', '--alarm-gib', '1e9')
        self.assertIn('ALARM', out)
        self.assertTrue(st['alarm'])

    def test_refuses_prepared_and_wrong_dirs(self):
        bad = self.tmp / 'prepared-x' / RUN
        bad.mkdir(parents=True)
        for d in [bad, self.tmp / 'stream']:
            r = subprocess.run([sys.executable, '-B', str(CLEANER), '--once', '--run-dir', str(d),
                                '--stats-out', '', '--sink-stats', str(self.stream / 'sink-stats.json'),
                                '--manifest', str(self.stream / 'manifest.jsonl')],
                               capture_output=True, text=True, timeout=60)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('refusing', r.stderr + r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
