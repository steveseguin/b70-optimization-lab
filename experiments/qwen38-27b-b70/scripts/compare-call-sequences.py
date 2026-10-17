#!/usr/bin/env python3
"""Compare two ctxkeeper call logs (--log-calls rows) call by call: kind, messages, prompt, cached, written, finish.
Prints the number of identical leading calls, the first difference and the calls around it (hang replay,
notes/2026-10-17-hang-repro.md). A call that failed has prompt None."""
import json
import sys

KEYS = ('kind', 'messages', 'prompt', 'cached', 'written', 'finish')


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


a, b = load(sys.argv[1]), load(sys.argv[2])
key = lambda r: tuple(r.get(k) for k in KEYS)
same = 0
for x, y in zip(a, b):
    if key(x) != key(y):
        break
    same += 1
print('calls: %d (reference) %d (replay); identical leading calls: %d' % (len(a), len(b), same))
print('fields:', KEYS)
for i in range(max(0, same - 3), min(max(len(a), len(b)), same + 4)):
    print(i, key(a[i]) if i < len(a) else None, '|', key(b[i]) if i < len(b) else None,
          '' if i < same else '<- differs' if i == same else '')
fail_a = next((i for i, r in enumerate(a) if not r.get('ok', True)), None)
fail_b = next((i for i, r in enumerate(b) if not r.get('ok', True)), None)
print('first failed call: reference %s, replay %s' % (fail_a, fail_b))
