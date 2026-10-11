#!/usr/bin/env python3
"""Coordinator-only exactness window; same packet2 watcher and ownership rules."""
import argparse
import json
from pathlib import Path
from common import BUILD, FIXTURES, LATCH, MANIFEST, MODES, admit, save, sha, teardown_ok, watch

def execute(card, output):
    out, manifest = admit(card, output)
    out.mkdir(parents=True)
    record = dict(schema='own-runtime.iq3.packet10.device-window.v1', passed=False, card=card,
        prepared_sha256=sha(MANIFEST), prepared_manifest=manifest, variants=[], device_executed=True)
    try:
        for mode in MODES:
            destination = out / mode
            command = [str(BUILD / 'device/device-test'), '--authorized-device-window', str(card), str(FIXTURES),
                str(destination / 'device.json'), str(destination / 'census.json'), mode]
            window = watch(command, destination)
            variant = dict(kernel=mode, passed=False, window=window)
            record['variants'].append(variant)
            if window.get('fault_lines') or window['stop_reason']:
                reason = window['stop_reason'] or 'kernel-journal fault'
                save(LATCH, dict(reason=reason, output=str(out), fault_lines=window.get('fault_lines', [])))
                record['outcome'] = 'kernel_fault' if window.get('fault_lines') else 'window_stopped'
                record['error'] = reason
                break
            raw = json.loads((destination / 'device.json').read_text())
            variant['native'] = raw
            if raw.get('failure_kind') == 'exactness':
                reason = 'exactness failed: ' + mode + ': ' + raw['error']
                record.update(outcome='exactness_failed', error=reason)
                save(LATCH, dict(reason=reason, output=str(out), fault_lines=[]))
                break
            if not teardown_ok(dict(raw, error='')):
                save(LATCH, dict(reason='unsafe teardown: ' + mode, output=str(out), fault_lines=[]))
            if raw.get('error'):
                raise ValueError(raw['error'])
            if window['returncode'] != 0:
                raise ValueError('native exit ' + str(window['returncode']))
            if not teardown_ok(raw):
                save(LATCH, dict(reason='unsafe teardown: ' + mode, output=str(out), fault_lines=[]))
                raise ValueError('unsafe teardown: ' + mode)
            if raw.get('checks') != manifest['fixture_cases'][mode]:
                raise ValueError('incomplete exactness coverage: ' + mode)
            variant['passed'] = True
        else:
            record.update(passed=True, outcome='passed')
    except Exception as e:
        record.update(outcome='aborted', error='aborted: ' + str(e))
    save(out / 'window.json', record)
    return record['passed']

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-device-window', action='store_true', required=True)
    p.add_argument('--card', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(0 if execute(a.card, a.output) else 1)
