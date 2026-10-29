#!/usr/bin/env python3
"""Cross-context dump comparison for research/tp/ctx131072-2026-10-29 (CPU only).

  xctx_compare.py RANK SMALL_RUN LARGE_RUN [--ratio 2]

SMALL_RUN and LARGE_RUN are rank-driver run directories (tp_rank1_driver.py / tp_rank0_driver.py) of the same harness
(same prompt rows, decode halves and speculation pattern) at context C and ratio*C. Every position the harness writes is
below C, so the large run must hold exactly the small run's state:
- target dump (rankR/state-2147483647: state-index.tsv + state.bundle, verified against state-seal-free per-buffer
  sha256 from the index): every buffer has the same name in both runs, and either the same bytes, or (a context-sized
  buffer) length ratio*L whose first L bytes hash to the small run's buffer and whose remaining bytes are all zero
  (position-major layouts: KV cache, pooled keys, select scores). Anything else differs. Equal-length buffers (the
  512-row QSA raw ring, every fixed-size buffer) must be bitwise equal.
- state.json fields other than buffers (histories, fp32 cache fields) equal.
- rank 0: the draft state (draft-final-state/all-state.json mutable_sha256): equal hashes, or for a context-sized
  buffer written out as a file (blk.N.qsa.{keys,values,pooled,raw}.bin) the same prefix rule on the file bytes.
- the driver summaries' decode tokens (rank 1 'tokens'; rank 0 'draft_tokens', 'prefill_draft_tokens', events) equal.
Prints one JSON line; exit 0 only if nothing differs."""
import argparse, hashlib, json, sys
from pathlib import Path

CHUNK = 1 << 24


def index(d):
    rows = {}
    lines = (d / 'state-index.tsv').read_text().split('\n')
    if not lines[0].startswith('GSQ_STATE_BUNDLE'):
        raise SystemExit(f'{d}: unexpected index header {lines[0]!r}')
    for line in lines[1:]:
        if line:
            name, start, length, h = line.split('\t')
            rows[name] = (int(start), int(length), h)
    return rows


def prefix_zero(f, start, length, head_len, want):
    """sha256 of [start, start+head_len) == want and [start+head_len, start+length) all zero."""
    f.seek(start)
    h, left = hashlib.sha256(), head_len
    while left:
        b = f.read(min(CHUNK, left))
        if not b:
            return False, 'short read'
        h.update(b); left -= len(b)
    if h.hexdigest() != want:
        return False, 'prefix differs'
    left = length - head_len
    while left:
        b = f.read(min(CHUNK, left))
        if not b:
            return False, 'short read'
        if b.count(0) != len(b):
            return False, 'tail not zero'
        left -= len(b)
    return True, 'prefix+zero'


def full_sha(f, start, length):
    f.seek(start); h, left = hashlib.sha256(), length
    while left:
        b = f.read(min(CHUNK, left)); h.update(b); left -= len(b)
    return h.hexdigest()


def compare_target(sd, ld, ratio):
    si, li = index(sd), index(ld)
    out = dict(exact=0, extended=[], differ=[], only_one_side=sorted(si.keys() ^ li.keys()))
    with open(ld / 'state.bundle', 'rb') as f:
        for name in sorted(si.keys() & li.keys()):
            (_, sl, sh), (lst, ll, lh) = si[name], li[name]
            if sl == ll and sh == lh:
                out['exact'] += 1
            elif ll == ratio * sl and sl > 0:
                ok, why = prefix_zero(f, lst, ll, sl, sh)
                (out['extended'] if ok else out['differ']).append(name if ok else dict(name=name, small=sl, large=ll, why=why))
            else:
                out['differ'].append(dict(name=name, small=sl, large=ll, why='length' if sl != ll else 'bytes'))
        # The index hashes are what the comparison trusts; spot-check that they match the bundle bytes of the large run.
        spot = [n for n in sorted(li) if li[n][1] <= (1 << 22)][:64]
        out['index_spot_checked'] = len(spot)
        bad = [n for n in spot if full_sha(f, li[n][0], li[n][1]) != li[n][2]]
        if bad:
            out['differ'].append(dict(name='index-integrity', bad=bad[:8]))
    return out


def compare_draft(sd, ld, ratio):
    a = json.loads((sd / 'all-state.json').read_text()); b = json.loads((ld / 'all-state.json').read_text())
    ma, mb = a['mutable_sha256'], b['mutable_sha256']
    out = dict(exact=0, extended=[], differ=[], only_one_side=sorted(ma.keys() ^ mb.keys()),
               other_fields_differ={k: (a.get(k), b.get(k)) for k in a.keys() | b.keys() if k != 'mutable_sha256' and a.get(k) != b.get(k)})
    for k in sorted(ma.keys() & mb.keys()):
        if ma[k] == mb[k]:
            out['exact'] += 1; continue
        fname = k.split(':')[-1] + '.bin'
        fs, fl = sd / fname, ld / fname
        if fs.exists() and fl.exists():
            ls_, ll = fs.stat().st_size, fl.stat().st_size
            if hashlib.sha256(fs.read_bytes()).hexdigest() != ma[k]:
                out['differ'].append(dict(name=k, why='small file hash differs from all-state.json')); continue
            if ll == ratio * ls_:
                with open(fl, 'rb') as f:
                    ok, why = prefix_zero(f, 0, ll, ls_, ma[k])
                full = hashlib.sha256(fl.read_bytes()).hexdigest() == mb[k]
                (out['extended'] if ok and full else out['differ']).append(k if ok and full else dict(name=k, why=why, large_file_matches_state=full))
                continue
        out['differ'].append(dict(name=k, why='hash (no comparable file)'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rank', type=int); ap.add_argument('small'); ap.add_argument('large'); ap.add_argument('--ratio', type=int, default=2)
    a = ap.parse_args()
    s, l = Path(a.small), Path(a.large)
    r = f'rank{a.rank}'
    sd, ld = s / r / 'state-2147483647', l / r / 'state-2147483647'
    res = dict(rank=a.rank, small=str(s), large=str(l), ratio=a.ratio)
    t = compare_target(sd, ld, a.ratio)
    js, jl = json.loads((sd / 'state.json').read_text()), json.loads((ld / 'state.json').read_text())
    t['other_fields_differ'] = {k: (js.get(k), jl.get(k)) for k in js.keys() | jl.keys() if k != 'buffers' and js.get(k) != jl.get(k)}
    t['buffers'] = len(index(sd))
    res['target'] = dict(t, extended_count=len(t['extended']))
    ss, sl = json.loads((s / 'summary.json').read_text()), json.loads((l / 'summary.json').read_text())
    keys = ('tokens',) if a.rank == 1 else ('draft_tokens', 'prefill_draft_tokens', 'events', 'kinds')
    res['summary_differ'] = [k for k in keys if ss.get(k) != sl.get(k)]
    res['steps_prompt'] = [(ss.get('steps'), ss.get('prompt')), (sl.get('steps'), sl.get('prompt'))]
    bad = bool(t['differ'] or t['only_one_side'] or t['other_fields_differ'] or res['summary_differ'] or res['steps_prompt'][0] != res['steps_prompt'][1])
    if a.rank == 0:
        d = compare_draft(s / r / 'draft-final-state', l / r / 'draft-final-state', a.ratio)
        res['draft'] = dict(d, extended_count=len(d['extended']))
        bad = bad or bool(d['differ'] or d['only_one_side'] or d['other_fields_differ'])
    res['passed'] = not bad
    print(json.dumps(res))
    return 0 if res['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
