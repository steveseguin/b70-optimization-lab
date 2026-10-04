#!/usr/bin/env python3
"""Packet 96 copy of missing-markers-93b.py (left untouched): done markers still missing for
the pipeline jobs that were ACTUALLY submitted.

    missing-markers-96.py --root R --run R/<run> <prefix> [<prefix> ...]

Same rules as 93b, except for batch-server sampler receipts (sampler_batch > 1): a
prompt only deposits its clip; the job holding it is submitted by the prompt that
completes the group (or ends the stream). So the expected sample markers are the real
clips of the jobs a receipt says it submitted (detail.submitted_job_clips), and a clip
deposited into a group that was never submitted (a stream cut short) expects nothing.
Batch-1 receipts follow the 93b rule. Reads files only.
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
                if (smp.get('sampler_batch') or 1) > 1:
                    for c in smp['detail'].get('submitted_job_clips') or []:
                        want.append('sample-%d' % c)
                else:
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
