#!/usr/bin/env python3
"""CPU checks for the tagged encode-ahead: no guessing, misses computed inline."""
import sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ltx_pipeline as p

def enc(text):
    def fn():
        time.sleep(0.02)
        return 'cond(' + text + ')'
    return fn

def run(index, depth, text, known):
    """known: dict index -> text of prompts already queued."""
    def lookahead(i):
        t = known.get(i)
        return None if t is None else (enc(t), 'sha:' + t)
    return p.run_ahead('encode', index, depth, enc(text), tag='sha:' + text, lookahead=lookahead)

p.clear()
# 1. Nothing queued: clip 0 computes inline, nothing started ahead.
v, d = run(0, 1, 'A', {})
assert v == 'cond(A)' and d['computed_inline'] and d['started_ahead'] == [] and not d['speculation_miss'], d
# 2. Clip 1 queued with a DIFFERENT text: clip 0 starts clip 1 with clip 1's text, not its own.
p.clear()
v, d = run(0, 1, 'A', {1: 'B'})
assert d['started_ahead'] == [{'index': 1, 'tag': 'sha:B'}], d
v, d = run(1, 1, 'B', {})
assert v == 'cond(B)' and d['queued_ahead'] and not d['computed_inline'] and not d['speculation_miss'], d
# 3. A queued job whose tag differs from the collecting prompt is discarded; inline result is the prompt's own.
p.clear()
p.submit('encode', 5, enc('STALE'), 'sha:STALE')
v, d = run(5, 1, 'FRESH', {})
assert v == 'cond(FRESH)' and d['speculation_miss'] and d['discarded_tag'] == 'sha:STALE' and d['computed_inline'], d
# 4. A tagged stage without a lookahead is refused (it would have to guess).
p.clear()
try:
    p.run_ahead('encode', 0, 1, enc('A'), tag='sha:A')
    raise SystemExit('expected refusal')
except RuntimeError as e:
    assert 'lookahead' in str(e)
# 5. Untagged legacy path still submits the same fn ahead (used by nothing now, kept explicit).
p.clear()
v, d = p.run_ahead('encode', 0, 2, enc('X'))
assert d['started_ahead'] == [{'index': 1, 'tag': None}, {'index': 2, 'tag': None}], d
# 6. run_behind is unchanged: prompt N emits N-depth; fill emits its own without consuming.
p.clear()
v, d = p.run_behind('decode', 0, 1, enc('d0'))
assert d['emitted_index'] == 0 and not d['primed'] and p.pending('decode') == [0], d
v, d = p.run_behind('decode', 1, 1, enc('d1'))
assert v == 'cond(d0)' and d['emitted_index'] == 0 and d['primed'] and p.pending('decode') == [1], d
p.clear()
print('ltx_pipeline lookahead checks: 6/6 passed')
