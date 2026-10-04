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
    assert L.verify_health_receipt(REAL, BOOT, END - datetime.timedelta(minutes=1)) == END   # small clock skew
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
    refuses(lambda: L.verify_health_receipt(mutated(cards=REAL['cards'][:3]), BOOT, now), 'four passing cards')
    bad = copy.deepcopy(REAL); bad['cards'][2]['pass'] = False
    refuses(lambda: L.verify_health_receipt(bad, BOOT, now), 'four passing cards')
    refuses(lambda: L.verify_health_receipt(mutated(device_count=3), BOOT, now), 'four passing cards')
    refuses(lambda: L.verify_health_receipt(mutated(schema='ltx.other.v1'), BOOT, now), 'schema')
    refuses(lambda: L.verify_health_receipt(mutated(journal_fault_lines_during_probe=['x CAT error']), BOOT, now),
            'during its own probe')
    refuses(lambda: L.verify_health_receipt(mutated(end_utc=None), BOOT, now), 'end_utc')
    refuses(lambda: L.verify_health_receipt(mutated(end_utc='yesterday'), BOOT, now), 'end_utc')


case('wrong boot / failed / stale / future / three cards / schema / probe faults refuse', refusal_case)


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
    for marker in ("    def watch_journal():", "def server_args(packet, run):", "def prepare_start(packet, digest, run_name):"):
        a = old[old.index(marker):]
        b = new[new.index(marker):]
        end_a = a.index('\n\n')          # the block up to its first blank line
        assert len(a[:end_a]) > 200 and a[:end_a + 2] == b[:end_a + 2], 'inherited block changed: ' + marker
    assert "    if health is None:\n        common.require(not FAULT.search(before), 'Kernel device or host fault in current boot')" in new
    assert old.split('# Additive host-kernel incident detection')[1].split('def write_json')[0].strip() in new, \
        'FAULT pattern changed'
    assert "if FAULT.search(journal):\n                fault('Kernel device or host fault', journal)" in new


case('without the option: whole-boot check, FAULT pattern and in-run watcher are the inherited ones', unchanged_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
