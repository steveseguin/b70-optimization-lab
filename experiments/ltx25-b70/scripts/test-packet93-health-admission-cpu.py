#!/usr/bin/env python3
"""CPU-only tests for packet 93's same-boot fault admission in the launcher
(scripts/serve-encoder-93.py, shipped as launch/serve-encoder.py). Nothing is
launched; no device, lock or journal is touched (journal text is synthetic).

1. A valid receipt (the real one from this boot, and synthetic copies) admits.
2. Wrong boot id, a failed receipt, a stale receipt (> 6 h), a future one, three
   cards, a failing card, a wrong schema, fault lines during the probe and a
   missing end time each refuse.
3. Journal: a fault line after the receipt refuses; earlier ones are returned
   as admitted.
4. Without the option the launcher's code path is the inherited one: the
   whole-boot check and the in-run watcher are byte-identical to packet 91b's.
"""
import copy
import datetime
import importlib.util
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
OLD = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91b/launch/serve-encoder.py')
RECEIPT = LANE / 'data/health/four-card-health-20261004T0325Z.json'
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-3:])))


def load_launcher():
    stub = types.ModuleType('encoder_runtime_common')

    def require(ok, message):
        if not ok:
            raise RuntimeError(message)

    stub.require = require
    sys.modules['encoder_runtime_common'] = stub
    spec = importlib.util.spec_from_file_location('serve_encoder_93', HERE / 'serve-encoder-93.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


L = load_launcher()
REAL = json.loads(RECEIPT.read_text())
END = L.parse_utc(REAL['end_utc'])
BOOT = REAL['boot_id']


def refuses(fn, text):
    try:
        fn()
    except RuntimeError as error:
        assert text in str(error), (text, str(error))
        return
    raise AssertionError('admitted: expected refusal containing %r' % text)


def admits_case():
    assert L.verify_health_receipt(REAL, BOOT, END + datetime.timedelta(minutes=1)) == END
    assert L.verify_health_receipt(REAL, BOOT, END + datetime.timedelta(hours=5, minutes=59)) == END
    assert L.verify_health_receipt(REAL, BOOT, END) == END                                    # end == now
    data, raw = L.load_health_receipt(RECEIPT)
    assert data == REAL and raw == RECEIPT.read_bytes()
    refuses(lambda: L.load_health_receipt(Path('data/health/x.json')), 'absolute')
    live = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    now = datetime.datetime.now(datetime.timezone.utc)
    if live == BOOT and now - END <= L.HEALTH_MAX_AGE:
        assert L.verify_health_receipt(REAL, live, now) == END


case('valid receipt admits (real receipt, this boot)', admits_case)


def refusal_case():
    now = END + datetime.timedelta(minutes=5)

    def mutated(**changes):
        r = copy.deepcopy(REAL)
        for k, v in changes.items():
            if v is None:
                r.pop(k, None)
            else:
                r[k] = v
        return r

    refuses(lambda: L.verify_health_receipt(REAL, '00000000-0000-0000-0000-000000000000', now), 'another boot')
    refuses(lambda: L.verify_health_receipt(mutated(passed=False), BOOT, now), 'did not pass')
    refuses(lambda: L.verify_health_receipt(mutated(passed='true'), BOOT, now), 'did not pass')
    refuses(lambda: L.verify_health_receipt(REAL, BOOT, END + datetime.timedelta(hours=6, seconds=1)), 'older than 6 hours')
    refuses(lambda: L.verify_health_receipt(REAL, BOOT, END - datetime.timedelta(minutes=10)), 'in the future')
    refuses(lambda: L.verify_health_receipt(REAL, BOOT, END - datetime.timedelta(seconds=1)), 'in the future')
    refuses(lambda: L.verify_health_receipt(mutated(cards=REAL['cards'][:3]), BOOT, now), 'four passing cards')
    bad = copy.deepcopy(REAL); bad['cards'][2]['pass'] = False
    refuses(lambda: L.verify_health_receipt(bad, BOOT, now), 'four passing cards')
    refuses(lambda: L.verify_health_receipt(mutated(device_count=3), BOOT, now), 'four passing cards')
    refuses(lambda: L.verify_health_receipt(mutated(schema='ltx.other.v1'), BOOT, now), 'schema')
    refuses(lambda: L.verify_health_receipt(mutated(journal_fault_lines_during_probe=['x CAT error']), BOOT, now),
            'during its own probe')
    refuses(lambda: L.verify_health_receipt(mutated(end_utc=None), BOOT, now), 'end_utc')
    refuses(lambda: L.verify_health_receipt(mutated(end_utc='yesterday'), BOOT, now), 'end_utc')
    # 93b: complete probe evidence is required, inside the probe's own thresholds
    bare = mutated(cards=[{'pass': True}] * 4)
    refuses(lambda: L.verify_health_receipt(bare, BOOT, now), 'four passing cards')
    for field in ('name', 'copy_roundtrip_exact', 'gemm_repeat_exact', 'gemm_fp32_max_abs_err',
                  'gemm_bf16_max_abs_err'):
        r = copy.deepcopy(REAL); del r['cards'][1][field]
        refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'card 1')
    r = copy.deepcopy(REAL); del r['cards'][2]['staged_from_previous_exact']
    refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'card 2')
    r = copy.deepcopy(REAL); r['cards'][3]['gemm_fp32_max_abs_err'] = 0.5
    refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'card 3')
    r = copy.deepcopy(REAL); r['cards'][0]['gemm_bf16_max_abs_err'] = 7.0
    refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'card 0')
    r = copy.deepcopy(REAL); r['cards'][0]['error'] = 'RuntimeError()'
    refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'card 0')
    r = copy.deepcopy(REAL); r['cards'][1]['device'] = 'xpu:0'
    refuses(lambda: L.verify_health_receipt(r, BOOT, now), 'devices')
    for key in ('kernel', 'torch', 'start_utc'):
        refuses(lambda: L.verify_health_receipt(mutated(**{key: None}), BOOT, now), 'lacks ' + key)
    refuses(lambda: L.verify_health_receipt(mutated(journal_fault_lines_during_probe=None), BOOT, now),
            'lacks that evidence')
    refuses(lambda: L.verify_health_receipt(mutated(start_utc='2026-10-04 04:00:00 UTC'), BOOT, now), 'ends before')


case('wrong boot / failed / stale / future / stripped evidence / out-of-threshold / schema refuse', refusal_case)


def signatures_case():
    import re
    probe = (HERE / 'check-four-card-health.py').read_text()
    pattern = re.search(r"FAULT = re.compile\(r'([^']+)'\)", probe).group(1)
    samples = {'Fault response': 'xe 0000:47:00.0: Fault response: Unsuccessful -ENOENT',
               'CAT error': 'Engine memory CAT error [18]: class=ccs',
               'engine reset': 'GT0: engine reset', 'Engine reset': 'GT0: Engine reset',
               'GPU HANG': 'GPU HANG: ecode 12', 'GuC.*reset': 'GuC firmware reset',
               'coredump': 'xe 0000:47:00.0: [drm] Xe device coredump has been created',
               'Timedout job': 'Timedout job: seqno=123, lrc_seqno=1, guc_id=2 in python [184372]',
               'wedged': 'xe 0000:47:00.0: [drm] device wedged, needs recovery'}
    assert set(pattern.split('|')) == set(samples), pattern
    for alt, line in samples.items():
        assert re.search(alt, line) and L.FAULT.search(line), 'launcher misses a probe signature: ' + alt
    src = (HERE / 'serve-encoder-93.py').read_text()
    i_since = src.index("    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')")
    i_before = src.index("    before = subprocess.check_output(['journalctl', '-k', '-b', '-o', 'short-unix', '--no-pager']")
    i_receipt = src.index("since_receipt = subprocess.check_output(['journalctl', '-k', '-b', '-o', 'short-unix', '--since', receipt['end_utc']")
    assert i_since < i_before < i_receipt, 'the watcher window must start before the admission snapshots'
    assert src.count("    since = datetime.datetime.now(") == 1
    assert "['journalctl', '-k', '-b', '-o', 'short-unix', '--since', since," in src


case('93b: one shared signature list covers the probe; journal coverage has no gap', signatures_case)


def boundary_case():
    # receipt end -> admission snapshot -> watcher (starts at or before the snapshot):
    # a fault logged between the snapshot and the old watcher start is in the watcher window.
    whole = 'Oct 04 02:46:41 kernel: xe 0000:47:00.0: [drm] Fault response: Unsuccessful\n'
    since_receipt = 'Oct 04 04:00:00 kernel: usb 1-2: new device\n'
    assert L.admit_journal(whole, since_receipt)
    watch = since_receipt + 'Oct 04 04:00:01 kernel: xe 0000:23:00.0: Timedout job: seqno=5 in python [9]\n'
    assert L.fault_lines(watch), 'watcher signature list misses a Timedout job line'
    refuses(lambda: L.admit_journal(whole, watch), 'after the health receipt')


case('93b: boundary lines (Timedout job right after the snapshot) are caught', boundary_case)


def journal_case():
    whole = ('Oct 04 02:46:41 steve-b70s kernel: xe 0000:47:00.0: [drm] Fault response: Unsuccessful -ENOENT\n'
             'Oct 04 02:46:41 steve-b70s kernel: xe 0000:47:00.0: [drm] Engine memory CAT error [18]: class=ccs\n'
             'Oct 04 02:50:00 steve-b70s kernel: usb 1-1: new device\n'
             'Oct 04 03:00:00 steve-b70s kernel: xe 0000:47:00.0: [drm] GT0: engine reset\n')
    clean = 'Oct 04 03:30:00 steve-b70s kernel: usb 1-2: new device\n'
    admitted = L.admit_journal(whole, clean)
    assert len(admitted) == 3 and all('xe 0000:47' in a for a in admitted), admitted
    later = clean + 'Oct 04 03:40:00 steve-b70s kernel: xe 0000:23:00.0: [drm] GT0: engine reset failed\n'
    refuses(lambda: L.admit_journal(whole, later), 'after the health receipt')
    refuses(lambda: L.admit_journal('', 'Oct 04 kernel: BUG: soft lockup - CPU#3 stuck for 23s!\n'),
            'after the health receipt')
    assert L.admit_journal('', '') == []


case('journal: a fault line after the receipt refuses; earlier ones are admitted', journal_case)


def unchanged_case():
    new = (HERE / 'serve-encoder-93.py').read_text()
    old = OLD.read_text()
    # 94d: the watcher now classifies (known xe GuC stall recorded, everything else latches)
    for marker in ("def server_args(packet, run):", "def prepare_start(packet, digest, run_name):"):
        a = old[old.index(marker):]
        b = new[new.index(marker):]
        end_a = a.index('\n\n')          # the block up to its first blank line
        assert len(a[:end_a]) > 200 and a[:end_a + 2] == b[:end_a + 2], 'inherited block changed: ' + marker
    old_alts = old.split("FAULT = re.compile(")[1].split(', re.I)')[0]
    new_alts = new.split("FAULT = re.compile(")[1].split(', re.I)')[0]
    assert old_alts.replace("coredump|'", "coredump|Timedout job|wedged|'") == new_alts, \
        'FAULT pattern changed beyond the two added signatures'
    assert ("verdict = classify_journal(journal)" in new and
            "if verdict['latch']:\n                fault('Kernel device or host fault', journal)" in new)
    assert "common.require(not classify_journal(before)['latch'], 'Kernel device or host fault in current boot')" in new


case('without the option: whole-boot check, FAULT pattern and in-run watcher are the inherited ones', unchanged_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
