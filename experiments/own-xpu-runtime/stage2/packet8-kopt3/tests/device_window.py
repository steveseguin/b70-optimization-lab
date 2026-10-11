#!/usr/bin/env python3
"""Coordinator-only exactness window; same packet2 watcher and ownership rules."""
import argparse
import json
from pathlib import Path
from common import BUILD, FIXTURES, LATCH, MANIFEST, MODES, admit, save, sha, teardown_ok, watch

def execute(card, output):
    out, manifest = admit(card, output)
    out.mkdir(parents=True)
    record = dict(schema='own-runtime.iq3.packet8.device-window.v1', passed=False, card=card,
        prepared_sha256=sha(MANIFEST), prepared_manifest=manifest, variants=[], device_executed=True)
    try:
        for mode in MODES:
            destination = out / mode
            command = [str(BUILD / 'device/device-test'), '--authorized-device-window', str(card), str(FIXTURES),
                str(destination / 'device.json'), str(destination / 'census.json'), mode]
            window = watch(command, destination)
            raw = json.loads((destination / 'device.json').read_text())
            passed = (window['returncode'] == 0 and window['stop_reason'] is None and teardown_ok(raw)
                      and raw.get('checks') == manifest['fixture_cases'][mode])
            record['variants'].append(dict(kernel=mode, passed=passed, window=window, native=raw))
            if not passed:
                raise ValueError('exactness failed: ' + mode)
        record['passed'] = True
    except Exception as e:
        record['error'] = str(e)
        save(LATCH, dict(reason=str(e), output=str(out)))
    save(out / 'window.json', record)
    return record['passed']

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-device-window', action='store_true', required=True)
    p.add_argument('--card', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(0 if execute(a.card, a.output) else 1)
