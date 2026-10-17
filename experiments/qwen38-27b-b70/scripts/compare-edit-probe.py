#!/usr/bin/env python3
"""Do two edit-cost probe runs give the same answers? Prints cached counts and waits side by side.

  python3 compare-edit-probe.py edit-K832.json edit-c27a.json [more.json ...]

The first file is the reference; every other file's answer text must equal it per (length, request). CPU only.
"""
import json
import sys


def load(path):
    return {(r['length'], r['request']): r for r in json.load(open(path))['rows']}


def main():
    ref, others = load(sys.argv[1]), [load(p) for p in sys.argv[2:]]
    bad = 0
    for key, r in ref.items():
        cells = [f"{r['cached_tokens']:>7} {r['first_token_s']:6.2f}s"]
        for o in others:
            x = o.get(key)
            if x is None:
                cells.append('missing')
                bad += 1
                continue
            same = x['text'] == r['text'] and x['prompt_tokens'] == r['prompt_tokens']
            bad += not same
            cells.append(f"{x['cached_tokens']:>7} {x['first_token_s']:6.2f}s {'same' if same else 'DIFFERENT'}")
        print(f'{key[0]:>6} {key[1]:<16} ' + ' | '.join(cells))
    print('answers different or missing:', bad)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
