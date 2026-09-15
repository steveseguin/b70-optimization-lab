#!/usr/bin/env python3
"""Compare b70_layer_hash call groups: first module whose output differs between identical requests.

Usage: compare-layer-hash-groups.py HASH_DIR [--groups 0,1,3]
Groups are numbered in request order for calls with the hashed token count. The
first group is the reference; for every other group, print the first differing
record (call order, module name, output slot) and how many records differ.
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('hash_dir', type=Path)
    ap.add_argument('--groups', default='')
    args = ap.parse_args()
    groups = {}
    for path in sorted(args.hash_dir.glob('hash-*.jsonl')):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            groups.setdefault(record['group'], []).append(record)
    wanted = [int(g) for g in args.groups.split(',')] if args.groups else sorted(groups)
    reference = groups[wanted[0]]
    print(f'reference group {wanted[0]}: {len(reference)} records')
    for group in wanted[1:]:
        records = groups[group]
        if [(r['name'], r.get('io'), r['slot']) for r in records] != [(r['name'], r.get('io'), r['slot']) for r in reference]:
            print(f'group {group}: module call order differs ({len(records)} records)')
            continue
        differing = [(a, b) for a, b in zip(reference, records) if a['sha256'] != b['sha256']]
        if not differing:
            print(f'group {group}: identical')
            continue
        first = differing[0][1]
        print(f"group {group}: {len(differing)} differing; first at call {first['index']} "
              f"{first['name']} slot {first['slot']} {first['shape']}")
        for a, b in differing[:6]:
            print(f"   {b['index']:5d} {b['name']} {b.get('io', 'out')} slot {b['slot']} "
                  f"ptr%64 {a.get('ptr_mod_64')}->{b.get('ptr_mod_64')} off {a.get('storage_offset')}->{b.get('storage_offset')}")


if __name__ == '__main__':
    main()
