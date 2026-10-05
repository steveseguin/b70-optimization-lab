#!/usr/bin/env python3
"""Packet 97: every emitted clip was decoded on the card its clip index selects (from receipts on disk).

    check-decode-placement-97.py --root R --run R/<run> --replicas <spec> <prefix> [<prefix> ...]

For every arm prefix, the submitted requests are R/requests/<prefix>-NN (prompt.json and
submission.json, written by the client). From each request's own submitted graph: the decode mode
(node 426 'mode'), the sampler depth SD (428 'depth'), the decode depth DD (426 'depth') and the
clip index (428 'clip_index'; prompt 00's is the arm's base). Prompt i must emit exactly clip
base + i - SD - DD (an explicit fill, detail.fill true and emitted_index -1, for i < SD + DD), the
packet 96 emission rule. Then every request must have a readable decode receipt
(pipeline-decode-<name>.json, written per prompt by the decode node) that:
- has passed true and the mode of the submitted graph;
- records decode_replica equal to the spec (rotation native, replica[, replica2]);
- emitted exactly the expected clip (or is an explicit fill);
- for an emitted clip, names in detail.decode_split the slot that mode selects for that clip index and
  that slot's card: pipeline-replica rotates native (xpu:3), replica, replica2 by clip index mod the
  number of slots; pipeline-save (the batch-1 placement probe) is native (xpu:3) for every clip.
The decode split is copied into the per-prompt receipt on disk when the prompt emits (a few clips after
the job ran), so nothing here depends on the server's bounded in-memory record of older clips.

Any missing, unreadable or malformed request or receipt, any other mode, an arm with no submitted
request or no emitted clip, fails. Writes JSON to stdout. Exit 0: all present and on their cards.
Exit 4: anything else.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SPECS = ('xpu:1', 'xpu:2', 'xpu:1,xpu:2', 'xpu:2,xpu:1')
MODES = ('pipeline-replica', 'pipeline-save')


def rotation(spec):
    cards = spec.split(',')
    slots = ['native', 'replica'] + ['replica%d' % (i + 1) for i in range(1, len(cards))]
    devices = {'native': 'xpu:3'}
    devices.update(zip(slots[1:], cards))
    return slots, devices


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_arm(root, run, spec, prefix):
    """(clips checked, problems) for one arm prefix."""
    slots, devices = rotation(spec)
    bad = []
    reqs = []
    pat = re.compile(re.escape(prefix) + r'-(\d{2,})')
    for req in (root / 'requests').glob(prefix + '-*'):
        m = pat.fullmatch(req.name)
        if m and (req / 'submission.json').is_file():
            reqs.append((int(m[1]), req))
    reqs.sort()
    if not reqs:
        return 0, ['%s: no submitted request' % prefix]
    if [i for i, _ in reqs] != list(range(len(reqs))):
        bad.append('%s: request numbers are not 0..%d' % (prefix, len(reqs) - 1))
    base = sd = dd = mode = None
    checked = 0
    for i, req in reqs:
        name = req.name
        try:
            g = json.loads((req / 'prompt.json').read_text())
            gmode, gdd = g['426']['inputs']['mode'], g['426']['inputs']['depth']
            gsd, gclip = g['428']['inputs']['depth'], g['428']['inputs']['clip_index']
        except (OSError, ValueError, KeyError, TypeError) as error:
            bad.append('%s: submitted graph unreadable or malformed (%r)' % (name, error))
            continue
        if not (_int(gdd) and _int(gsd) and _int(gclip)) or gmode not in MODES:
            bad.append('%s: submitted graph mode %r / depths %r %r / clip %r not admitted' % (name, gmode, gsd, gdd, gclip))
            continue
        if base is None:
            base, sd, dd, mode = gclip - i, gsd, gdd, gmode
        elif (gsd, gdd, gmode) != (sd, dd, mode) or gclip != base + i:
            bad.append('%s: graph differs from the arm (mode/depths/clip index)' % name)
            continue
        expect = base + i - sd - dd if i >= sd + dd else -1
        try:
            dec = json.loads((run / ('pipeline-decode-' + name + '.json')).read_text())
        except (OSError, ValueError) as error:
            bad.append('%s: decode receipt missing or unreadable (%r)' % (name, error))
            continue
        if not isinstance(dec, dict) or dec.get('passed') is not True:
            bad.append('%s: decode receipt did not pass' % name)
            continue
        if dec.get('mode') != gmode:
            bad.append('%s: receipt mode %r, submitted graph %r' % (name, dec.get('mode'), gmode))
            continue
        rec = dec.get('decode_replica') or {}
        if rec.get('replica_devices') != spec.split(',') or rec.get('rotation') != slots:
            bad.append('%s: receipt placement %r, expected %s' % (name, rec, spec))
            continue
        detail = dec.get('detail')
        e = detail.get('emitted_index') if isinstance(detail, dict) else None
        if not _int(e):
            bad.append('%s: malformed emitted_index %r' % (name, e))
            continue
        if e != expect:
            bad.append('%s: emitted clip %d, expected %d' % (name, e, expect))
            continue
        if e < 0:
            if detail.get('fill') is not True:
                bad.append('%s: emitted nothing without an explicit fill' % name)
            continue
        want = slots[e % len(slots)] if gmode == 'pipeline-replica' else 'native'
        split = detail.get('decode_split')
        checked += 1
        if not isinstance(split, dict) or split.get('slot') != want or split.get('device') != devices[want]:
            bad.append('%s: clip %d expected on %s/%s, found %r' % (
                name, e, want, devices[want],
                [split.get('slot'), split.get('device')] if isinstance(split, dict) else split))
    if checked == 0 and not bad:
        bad.append('%s: no emitted clip to check' % prefix)
    return checked, bad


def check(root, run, spec, prefixes):
    checked, bad, per = 0, [], {}
    for prefix in prefixes:
        c, b = check_arm(root, run, spec, prefix)
        per[prefix] = {'clips_checked': c, 'problems': len(b)}
        checked += c
        bad += b
    return checked, bad, per


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--replicas', required=True, choices=SPECS)
    ap.add_argument('prefixes', nargs='+')
    a = ap.parse_args(argv)
    checked, bad, per = check(a.root, a.run, a.replicas, a.prefixes)
    slots, devices = rotation(a.replicas)
    print(json.dumps({'schema': 'ltx.decode-placement-check-97.v2', 'replicas': a.replicas, 'rotation': slots,
                      'devices': devices, 'arms': per, 'clips_checked': checked, 'problems': bad[:50],
                      'problem_count': len(bad), 'passed': checked > 0 and not bad}, indent=2))
    return 0 if checked > 0 and not bad else 4


if __name__ == '__main__':
    sys.exit(main())
