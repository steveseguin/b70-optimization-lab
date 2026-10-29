#!/usr/bin/env python3
"""Symbolise an alloc_trace log offline (research/tp/fault-ladder-2026-10-29). CPU only.

  symbolize.py LOG MAPS [--min BYTES] [--after-ns NS] [--json OUT]

Groups logged events by (kind, call stack), prints each group's count, sizes and threads with its frames resolved through
the process's /proc/self/maps copy (file offset -> ELF vaddr via PT_LOAD headers, then addr2line -f -C -i; return
addresses minus 1)."""
import argparse, bisect, collections, json, re, subprocess, sys


def load_maps(path):
    rows = []
    for line in open(path):
        p = line.split()
        if len(p) < 6 or not p[5].startswith('/'):
            continue
        a, b = (int(x, 16) for x in p[0].split('-'))
        rows.append((a, b, int(p[2], 16), p[5]))
    rows.sort()
    return rows


_loads = {}
def loads(path):
    if path not in _loads:
        out = subprocess.run(['readelf', '-lW', path], capture_output=True, text=True).stdout
        segs = []
        for line in out.splitlines():
            p = line.split()
            if p and p[0] == 'LOAD':
                segs.append((int(p[1], 16), int(p[2], 16), int(p[4], 16)))  # offset, vaddr, filesz
        _loads[path] = segs
    return _loads[path]


def to_file(addr, maps, starts):
    i = bisect.bisect_right(starts, addr) - 1
    if i < 0:
        return None
    a, b, off, path = maps[i]
    if not a <= addr < b:
        return None
    foff = addr - a + off
    for o, v, sz in loads(path):
        if o <= foff < o + max(sz, 1):
            return path, foff - o + v
    return path, foff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log'); ap.add_argument('maps')
    ap.add_argument('--min', type=int, default=0); ap.add_argument('--after-ns', type=int, default=0)
    ap.add_argument('--json')
    a = ap.parse_args()
    maps = load_maps(a.maps); starts = [m[0] for m in maps]
    events = []
    for line in open(a.log):
        if line.startswith('#') or '|' not in line:
            continue
        head, frames = line.split('|', 1)
        t, tid, kind, size, old, ptr, minflt = head.split()
        t, size = int(t), int(size)
        if t < a.after_ns or (kind != 'free' and size < a.min):
            continue
        events.append(dict(t=t, tid=int(tid), kind=kind, size=size, old=old, ptr=ptr, minflt=int(minflt),
                           frames=tuple(int(x, 16) for x in frames.split())))
    # resolve every distinct frame
    per_file = collections.defaultdict(set)
    loc = {}
    for e in events:
        for f in e['frames']:
            if f in loc:
                continue
            r = to_file(f - 1, maps, starts)
            loc[f] = r
            if r:
                per_file[r[0]].add(r[1])
    names = {}
    for path, vs in per_file.items():
        vs = sorted(vs)
        out = subprocess.run(['addr2line', '-f', '-C', '-e', path] + [hex(v) for v in vs], capture_output=True, text=True).stdout.splitlines()
        for i, v in enumerate(vs):
            fn = out[2 * i] if 2 * i < len(out) else '??'
            names[(path, v)] = fn
    def sym(f):
        r = loc.get(f)
        if not r:
            return hex(f)
        return f"{names.get(r, '??')} [{r[0].rsplit('/', 1)[-1]}+{r[1]:#x}]"
    groups = collections.OrderedDict()
    for e in events:
        key = (e['kind'], e['frames'][:12])
        groups.setdefault(key, []).append(e)
    report = []
    for (kind, frames), es in sorted(groups.items(), key=lambda kv: -sum(x['size'] for x in kv[1])):
        sizes = collections.Counter(x['size'] for x in es)
        g = dict(kind=kind, count=len(es), total_bytes=sum(x['size'] for x in es), threads=sorted({x['tid'] for x in es}),
                 sizes=sorted(sizes.items())[:24], first_ns=es[0]['t'], last_ns=es[-1]['t'], frames=[sym(f) for f in frames])
        report.append(g)
        print(f"== {kind} x{len(es)} total {g['total_bytes']} threads {g['threads']}")
        print('   sizes', g['sizes'])
        for s in g['frames']:
            print('    ', s[:220])
    if a.json:
        json.dump(dict(log=a.log, events=len(events), groups=report), open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
