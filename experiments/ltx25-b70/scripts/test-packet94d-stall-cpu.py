#!/usr/bin/env python3
"""CPU-only tests for packet 94d's tolerance of the known xe GuC host stall (launcher
classification, receipts and summary), using the real journal excerpts.

1. The known stall (hard LOCKUP with xe_guc_irq_handler / g2h_read in its same-second
   trace, plus a soft lockup within 180 s) is recorded and does not latch:
   R/encoder-server-shard4-94c-shard3-c/journal-fault.txt and both lockup excerpts.
2. A soft lockup without the xe hard-lockup signature latches; so does one more
   than 180 s after it; a hard lockup whose trace lacks the xe signature does not
   excuse a following soft lockup.
3. A GPU fault inside a stall window latches (the 2026-10-04 02:46 excerpt).
4. Admission (journal since the health receipt) uses the same classification.
5. Events are written once each to host-stalls.jsonl; the sampler marks
   overlapping requests; the summary drops stalled intervals from speed statistics
   and counts them.
"""
import importlib.util
import json
import re
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EVID = REPO / 'data/2026-10-03-xe-guc-hard-lockup'
FAULT94C = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-shard4-94c-shard3-c/journal-fault.txt')
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-3:])))


stub = types.ModuleType('encoder_runtime_common')


def _require(ok, message):
    if not ok:
        raise RuntimeError(message)


stub.require = _require
sys.modules['encoder_runtime_common'] = stub
spec = importlib.util.spec_from_file_location('launcher94d', HERE / 'serve-encoder-93.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def known_case():
    for path in (FAULT94C, EVID / 'lockup-1-kernel-7.0.0-38.txt', EVID / 'lockup-2-kernel-7.0.0-38.txt'):
        text = path.read_text()
        assert L.FAULT.search(text) or 'hard LOCKUP' in text
        v = L.classify_journal(text, year=2026)
        assert v['latch'] is False and v['stalls'], (path.name, v['gpu_faults'], v['unexplained_host'])
        for e in v['stalls']:
            assert L.XE_STALL_TRACE.search(e['trace']) and 'hard LOCKUP on cpu' in e['anchor']
    v = L.classify_journal(FAULT94C.read_text(), year=2026)
    e, = v['stalls']
    assert any('soft lockup - CPU#20 stuck for 26s' in l for l in e['lines']) and e['duration_s'] == 36.0, e
    # the 94c launcher's old rule latched this exact journal
    assert L.FAULT.search(FAULT94C.read_text())


case('known xe GuC stall (real excerpts): recorded, not latched', known_case)


def latch_case():
    text = FAULT94C.read_text().splitlines()
    soft = [l for l in text if 'soft lockup' in l]
    assert L.classify_journal('\n'.join(soft), year=2026)['latch'] is True          # no xe hard lockup before it
    # hard lockup whose trace lacks the xe signature
    stripped = [l for l in text if not L.XE_STALL_TRACE.search(l)]
    v = L.classify_journal('\n'.join(stripped), year=2026)
    assert v['latch'] is True and not v['stalls']
    # a soft lockup more than 180 s after the anchor
    late = text + [re.sub(r'10:33:17', '10:36:52', soft[0])]
    v = L.classify_journal('\n'.join(late), year=2026)
    assert v['latch'] is True and len(v['unexplained_host']) == 1
    # RCU stall and blocked-task inside the window are part of the event; clocksource alone never latches
    extra = text + ['Oct 04 10:33:40 steve-b70s kernel: rcu: INFO: rcu_preempt detected stalls on CPUs/tasks:',
                    'Oct 04 10:34:00 steve-b70s kernel: clocksource: Long readout interval, skipping watchdog check']
    v = L.classify_journal('\n'.join(extra), year=2026)
    assert v['latch'] is False and len(v['stalls'][0]['lines']) == 4, v['stalls'][0]['lines']
    assert L.classify_journal('Oct 04 11:00:00 h kernel: clocksource: Long readout interval', year=2026)['latch'] is False


case('soft lockup without the xe signature, or outside 180 s, latches', latch_case)


def gpu_in_window_case():
    v = L.classify_journal((EVID / 'kernel-20261004T0245Z-lockups-and-cat-error.txt').read_text(), year=2026)
    assert v['latch'] is True and v['stalls'] and any('Fault response' in l for l in v['gpu_faults'])
    t = FAULT94C.read_text() + 'Oct 04 10:33:00 steve-b70s kernel: xe 0000:43:00.0: [drm] Tile0: GT0: Fault response: Unsuccessful -ENOENT\n'
    v = L.classify_journal(t, year=2026)
    assert v['latch'] is True and len(v['gpu_faults']) == 1
    for sig in ('CAT error [18]', 'Engine reset: engine_class=ccs', 'GPU HANG', 'GuC firmware reset', 'devcoredump',
                'Timedout job: seqno=1', 'device wedged'):
        assert L.classify_journal(FAULT94C.read_text() + 'Oct 04 10:33:05 h kernel: ' + sig + '\n',
                                  year=2026)['latch'] is True, sig


case('a GPU fault inside a stall window still latches', gpu_in_window_case)


def admission_and_format_case():
    raw = FAULT94C.read_text()
    assert L.admit_journal('', raw) is not None                       # admitted: known stall only
    try:
        L.admit_journal('', raw + 'Oct 04 10:33:02 h kernel: GT0: Engine reset: engine_class=bcs\n')
        raise AssertionError('admitted a GPU fault')
    except RuntimeError as error:
        assert 'after the health receipt' in str(error)
    # the launcher reads short-unix; the same journal in that format classifies the same
    base = L.line_time(raw.splitlines()[0], 2026)
    unix = '\n'.join('%.6f %s' % (base + (L.line_time(l, 2026) or base) - base, l.split(' ', 3)[3])
                     if L.line_time(l, 2026) else l for l in raw.splitlines())
    v = L.classify_journal(unix)
    assert v['latch'] is False and len(v['stalls']) == 1
    iso = (EVID / 'lockup-2-kernel-7.0.0-38.txt').read_text()
    assert L.line_time(iso.splitlines()[0]) is not None


case('admission uses the same classification; short-unix and ISO journals parse', admission_and_format_case)


def records_case():
    v = L.classify_journal(FAULT94C.read_text(), year=2026)
    with tempfile.TemporaryDirectory() as t:
        path = Path(t) / 'host-stalls.jsonl'
        seen = set()
        L.record_stalls(path, v['stalls'], seen)
        L.record_stalls(path, v['stalls'], seen)                     # repeated polls: written once
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        assert len(rows) == 1 and rows[0]['kind'] == 'xe-guc-hard-lockup' and len(rows[0]['window_unix']) == 2
        src = (HERE / 'pipeline_sampler_node.py').read_text()
        ns = {'Path': Path, 'json': json}
        exec(compile(src[src.index('def stall_overlaps'):src.index('def placement_devices')], 'psn', 'exec'), ns)
        a, b = rows[0]['window_unix']
        assert ns['stall_overlaps'](path, a - 5, a + 1) and not ns['stall_overlaps'](path, b + 1, b + 9)
        sspec = importlib.util.spec_from_file_location('summ', HERE / 'summarize-campaign-93.py')
        S = importlib.util.module_from_spec(sspec)
        sspec.loader.exec_module(S)
        stalls = S.load_stalls(Path(t))
        assert len(stalls) == 1
        rows_tp = [{'prompt': 'p%d' % i, 'fill': False, 'reference': 'r', 't_done': a - 6 + 2 * i, 'exact': True}
                   for i in range(30)]
        kept, dropped = S.stall_filtered_intervals(rows_tp, stalls)
        assert dropped > 0 and len(kept) + dropped == 29 and all(k == 2 for k in kept), (kept, dropped)


case('events written once; sampler marks overlaps; summary drops stalled intervals', records_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
