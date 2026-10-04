#!/usr/bin/env python3
"""Packet 93b: done markers still missing for the pipeline jobs that were ACTUALLY submitted.

    missing-markers-93b.py --root R --run R/<run> <prefix> [<prefix> ...]

Prints one line per missing marker (sample-<i>, decode-<i>, save-<i>); prints
nothing when every submitted job has finished. A job counts as submitted only
from the server's own receipts of a prompt the client really submitted
(requests/<prefix>-NN/submission.json):
- sample job <clip_index>: the sampler receipt carries `detail` (run_behind
  returned, so the job was queued);
- decode job <clip_index of the decode receipt>: the decode receipt carries
  `detail.saved_file` (run_behind returned; upstream fills submit nothing);
- save <i>: queued by decode job <i>, so expected once decode-<i> is done.
A prompt that failed before its node queued anything expects nothing, so a
stop never waits for jobs that never existed. Reads files only.
"""
import argparse
import json
import re
from pathlib import Path


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def submitted(root, prefix):
    names = []
    for req in (root / 'requests').glob(prefix + '-*'):
        if re.fullmatch(re.escape(prefix) + r'-\d{2,}', req.name) and (req / 'submission.json').is_file():
            names.append(req.name)
    return sorted(names)


def expected(root, run, prefixes):
    want = []
    for prefix in prefixes:
        for name in submitted(root, prefix):
            smp = load(run / ('pipeline-sampler-' + name + '.json'))
            if isinstance(smp, dict) and isinstance(smp.get('detail'), dict) and isinstance(smp.get('clip_index'), int):
                want.append('sample-%d' % smp['clip_index'])
            dec = load(run / ('pipeline-decode-' + name + '.json'))
            if (isinstance(dec, dict) and isinstance(dec.get('detail'), dict) and 'saved_file' in dec['detail']
                    and isinstance(dec.get('clip_index'), int) and dec['clip_index'] >= 0):
                i = dec['clip_index'] - int(dec.get('upstream_depth') or 0)
                want.append('decode-%d' % i)
                if (run / ('pipeline-done-decode-%d.json' % i)).is_file():
                    want.append('save-%d' % i)
    return want


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('prefixes', nargs='*')
    a = ap.parse_args(argv)
    missing = [m for m in expected(a.root, a.run, a.prefixes)
               if not (a.run / ('pipeline-done-%s.json' % m)).is_file()]
    for m in missing:
        print(m)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
