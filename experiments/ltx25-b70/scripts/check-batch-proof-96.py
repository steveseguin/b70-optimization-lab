#!/usr/bin/env python3
"""Packet 96: the in-server, full-model versions of the probe's neighbour and slot tests.

    check-batch-proof-96.py --prereg data/stability-01-batch<B>-prereg.json \
        --arm <throughput.json> --kind neighbours|slots|timed [--out <json>]

The reference set was sampled in one fixed arrangement (recorded per fixture in the
prereg). A proof arm regenerates the fixtures in a different arrangement and must
reproduce every reference byte for byte (all four raw outputs, compared by the client
against exactly this prereg's references):

- neighbours: every fixture is emitted at least once, and every emitted clip had a
  different set of neighbour fixtures than in each of its reference occurrences;
- slots: every fixture is emitted at least once, and every emitted clip sat in a
  different slot than in each of its reference occurrences;
- timed: every emitted clip is exact; the variety of batch compositions is reported.

Every kind (review finding 4): the arm must have emitted exactly clips 0..K-1 in
prompt order (K = --expect-clips, the runner's count from the depth formula), each
once, each the fixture the arm's own order assigns to it; an empty arm, a missing,
extra or duplicated clip rejects. The batch provenance of every clip must name the
clip itself at its slot.

Exit 0: passed. Exit 15: not byte-identical or the arrangement did not differ as
required. Exit 1: unreadable input. Reads files only.
"""
import argparse
import json
import sys
from pathlib import Path


def evaluate(prereg, tp, kind, expect_clips):
    problems = []
    if not isinstance(expect_clips, int) or expect_clips <= 0:
        problems.append('expected clip count must be positive (got %r)' % (expect_clips,))
    emitted = [r for r in tp.get('rows', []) if r.get('emitted_index', -1) >= 0]
    seq = [r['emitted_index'] for r in emitted]
    if not seq:
        problems.append('the arm emitted no clip')
    dups = sorted({e for e in seq if seq.count(e) > 1})
    if dups:
        problems.append('clips emitted more than once: %s' % dups)
    if seq != list(range(expect_clips or 0)):
        problems.append('emitted clips %s, expected 0..%d in prompt order' % (seq[:40], (expect_clips or 0) - 1))
    order = tp.get('fixture_order') or []
    for r in emitted:
        e = r['emitted_index']
        if r.get('duplicate') or r.get('fill'):
            problems.append('%s: clip %d marked duplicate/fill' % (r['prompt'], e))
        if not (0 <= e < len(order)) or r.get('emitted_fixture') != order[e]:
            problems.append('%s: clip %d is %r, the arm order says %r' % (
                r['prompt'], e, r.get('emitted_fixture'), order[e] if 0 <= e < len(order) else None))
        info = r.get('batch') or {}
        rows_ = info.get('rows') or []
        slot = info.get('slot')
        if not (isinstance(slot, int) and 0 <= slot < len(rows_) and
                rows_[slot] == tp.get('index_base', 0) + e):
            problems.append('%s: batch provenance does not name clip %d at its slot' % (r['prompt'], e))
    refs = {f['id']: f for f in prereg['fixtures']}
    want_refs = {f['reference'] for f in prereg['fixtures']}
    if tp.get('batch') != prereg.get('batch'):
        problems.append('arm batch %r, references batch %r' % (tp.get('batch'), prereg.get('batch')))
    rows = [r for r in tp['rows'] if r.get('emitted_index', -1) >= 0 and not r.get('fill')]
    seen = {}
    for r in rows:
        fx = r.get('emitted_fixture')
        if r.get('reference') not in want_refs or r.get('reference') != refs.get(fx, {}).get('reference'):
            problems.append('%s compared against %r, not the batch reference of %s' % (r['prompt'], r.get('reference'), fx))
        if r.get('exact') is not True:
            problems.append('%s (%s): not byte-identical to %s' % (r['prompt'], fx, r.get('reference')))
        info = r.get('batch') or {}
        if info.get('batch') != prereg.get('batch'):
            problems.append('%s: emitted from a job of batch %r' % (r['prompt'], info.get('batch')))
            continue
        seen.setdefault(fx, []).append((info.get('slot'), info.get('neighbour_fixtures')))
        occ = refs.get(fx, {}).get('arrangement', {}).get('occurrences', [])
        if kind == 'neighbours':
            same = [o for o in occ if o['neighbour_fixtures'] == info.get('neighbour_fixtures')]
            if same:
                problems.append('%s (%s): same neighbours %s as in the reference arm' % (
                    r['prompt'], fx, info.get('neighbour_fixtures')))
        elif kind == 'slots':
            same = [o for o in occ if o['slot'] == info.get('slot')]
            if same:
                problems.append('%s (%s): same slot %s as in the reference arm' % (r['prompt'], fx, info.get('slot')))
    if kind in ('neighbours', 'slots'):
        missing = sorted(set(refs) - set(seen))
        if missing:
            problems.append('fixtures not emitted: %s' % missing)
    variety = {fx: len({(s, tuple(n or [])) for s, n in v}) for fx, v in sorted(seen.items())}
    return {'kind': kind, 'batch': prereg.get('batch'), 'expected_clips': expect_clips, 'references': sorted(want_refs)[:1] + ['...'],
            'reference_prereg_campaign': prereg.get('campaign'), 'clips_checked': len(rows),
            'clips_exact': sum(1 for r in rows if r.get('exact') is True),
            'fixtures_emitted': sorted(seen), 'arrangements_per_fixture': variety,
            'passed': not problems, 'problems': problems[:40]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--prereg', required=True, type=Path)
    ap.add_argument('--arm', required=True, type=Path)
    ap.add_argument('--kind', required=True, choices=('neighbours', 'slots', 'timed'))
    ap.add_argument('--expect-clips', type=int, required=True)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args(argv)
    try:
        prereg = json.loads(a.prereg.read_text())
        tp = json.loads(a.arm.read_text())
    except (OSError, ValueError) as error:
        print(json.dumps({'passed': False, 'problems': ['unreadable: %r' % error]}))
        return 1
    result = evaluate(prereg, tp, a.kind, a.expect_clips)
    result.update({'arm': str(a.arm), 'prereg': str(a.prereg)})
    text = json.dumps(result, indent=1)
    if a.out:
        a.out.write_text(text + '\n')
    print(text)
    return 0 if result['passed'] else 15


if __name__ == '__main__':
    sys.exit(main())
