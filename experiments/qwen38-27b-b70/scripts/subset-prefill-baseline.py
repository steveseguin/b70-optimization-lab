#!/usr/bin/env python3
"""Derive a bench-prefill-followup baseline restricted to some of its prompt lengths.

The tool compares a candidate only with a baseline whose prompt set is identical, so a reference recorded at six
lengths cannot gate a profile that serves five. This keeps the reference's rows, prompts and hashes for the selected
lengths only (no output is altered) and records the source summary's SHA-256.

usage: subset-prefill-baseline.py --source .../summary.json --lengths 2048,8192,16384,24576,30720 --out .../summary.json
"""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--lengths', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    keep = {int(x) for x in a.lengths.split(',')}
    data = a.source.read_bytes()
    s = json.loads(data)
    if s.get('passed') is not True:
        raise SystemExit('source did not pass')

    def wanted(key):
        return int(key.rsplit('-', 1)[1]) in keep

    s['prompts'] = {k: v for k, v in s['prompts'].items() if wanted(k)}
    s['prompt_sha256s'] = {k: v for k, v in s['prompt_sha256s'].items() if wanted(k)}
    s['rows'] = [r for r in s['rows'] if wanted(r['key'])]
    s['by_length'] = {k: v for k, v in s['by_length'].items() if int(k) in keep}
    if 'lengths' in s.get('args', {}):
        s['args']['lengths'] = ','.join(str(x) for x in sorted(keep))
    s.setdefault('notes', [])
    s['notes'] = list(s['notes']) + [f'subset of {a.source} (sha256 {hashlib.sha256(data).hexdigest()}) restricted to lengths {sorted(keep)}; outputs unchanged']
    if a.out.exists():
        raise SystemExit(f'refusing to overwrite {a.out}')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(s, indent=1) + '\n')
    print(f'wrote {a.out}: {len(s["rows"])} rows, lengths {sorted(keep)}')


if __name__ == '__main__':
    main()
