#!/usr/bin/env python3
"""Distinct experts per M-row chunk from the engine's OWNRT_PREFILL_ROUTE_DUMP file (research/decode-site-census-2026-10-30).

Record (prefill_engine.hpp): u32 label length, label, u32 rows M, u32 slots (M*10), then slots x {expert_id, row_begin,
row_count} (u32 each); slot s belongs to row s // 10. Only the gate site of each layer is used (up/down repeat the routes).
A census_driver.py --route-dump run reads, per mode, a prefix chunk (M = prefix rows) then the window in M-row chunks."""
import collections, json, struct, sys
from pathlib import Path


def records(path):
    b = Path(path).read_bytes()
    o = 0
    while o < len(b):
        (n,) = struct.unpack_from('<I', b, o); o += 4
        label = b[o:o + n].decode(); o += n
        M, slots = struct.unpack_from('<II', b, o); o += 8
        r = struct.unpack_from(f'<{3 * slots}I', b, o); o += 12 * slots
        yield label, M, [r[3 * i] for i in range(slots)]


def chunks(run):
    """{mode: [ {layer: [expert set per row]} per chunk ]} for the window chunks of each mode."""
    s = json.loads((Path(run) / 'summary.json').read_text())
    K, modes = s['prefix'], [m for m in s['modes']]
    out, mi, cur, last_M = collections.defaultdict(list), -1, None, None
    for label, M, ex in records(Path(run) / 'routes.bin'):
        if not label.endswith('.expsgate'):
            continue
        layer = int(label.split('.')[1])
        if M == K or M > 8:   # a prefix chunk starts the next mode's request
            if last_M is None or last_M <= 8:
                mi += 1
            last_M = M
            continue
        if last_M is None or last_M > 8 or layer in cur:
            cur = {}
            out[modes[mi]].append(cur)
        last_M = M
        top = len(ex) // M
        cur[layer] = [set(ex[r * top:(r + 1) * top]) for r in range(M)]
    return s, dict(out)


def stats(run):
    s, by_mode = chunks(run)
    res = {}
    for mode, chs in by_mode.items():
        M = int(mode)
        d = [len(set().union(*rows)) for ch in chs for rows in ch.values() if len(rows) == M]
        pair = [len(rows[i] | rows[i + 1]) for ch in chs for rows in ch.values() for i in range(len(rows) - 1)]
        per_layer = collections.defaultdict(list)
        for ch in chs:
            for layer, rows in ch.items():
                if len(rows) == M:
                    per_layer[layer].append(len(set().union(*rows)))
        res[mode] = dict(rows=M, chunks=len(chs), samples=len(d), distinct_mean=sum(d) / len(d), distinct_min=min(d), distinct_max=max(d),
                         slots=10 * M, shared_fraction=1 - (sum(d) / len(d)) / (10 * M),
                         adjacent_pair_distinct_mean=(sum(pair) / len(pair)) if pair else None,
                         per_layer_mean={str(k): sum(v) / len(v) for k, v in sorted(per_layer.items())},
                         per_chunk_layer=[{str(l): len(set().union(*rows)) for l, rows in ch.items()} for ch in chs])
    return res


if __name__ == '__main__':
    r = stats(sys.argv[1])
    for mode, v in r.items():
        print(mode, {k: v[k] for k in ('chunks', 'samples', 'distinct_mean', 'distinct_min', 'distinct_max', 'slots', 'shared_fraction', 'adjacent_pair_distinct_mean')})
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(r, indent=1))
