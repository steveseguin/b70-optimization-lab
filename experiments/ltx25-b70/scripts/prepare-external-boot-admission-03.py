#!/usr/bin/env python3
"""Write the boot-03 health admission after the user-confirmed 2026-09-17 restart.

Metadata only: no Torch import, no device query, no latch change. Pins this
boot, the unchanged FAULT bytes, the complete kernel prefix so far, the original
runtime fingerprint, packet 61's manifest, the render mapping and the ordinal
device properties recorded by the faulted server itself.
"""
import datetime, hashlib, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / 'scripts'))
import encoder_runtime_common as common

FIELDS = ('__CURSOR', '_BOOT_ID', '__MONOTONIC_TIMESTAMP', '__REALTIME_TIMESTAMP', 'MESSAGE', 'PRIORITY')
OUT = LANE / 'data/external-boot-health-03'
OUT.mkdir(exist_ok=False)
canonical = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
raw = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', '-o', 'json'], text=True, timeout=10)
records = [{k: r[k] for k in FIELDS} for r in map(json.loads, raw.splitlines())]
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert all(r['_BOOT_ID'] == boot.replace('-', '') for r in records)
faulted = json.loads((common.ROOT / 'encoder-server-graph-capture-58/server-identity.json').read_text())
packet = common.ROOT / 'prepared-encoder-graph-capture-61'
admission = {
    'schema': 'ltx.external-boot-health-admission.v2',
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'boot_id': boot,
    'fault_sha256': common.sha(common.ROOT / 'FAULT.json'),
    'journal_prefix_count': len(records),
    'journal_prefix_sha256': canonical(records),
    'journal_last_monotonic_us': int(records[-1]['__MONOTONIC_TIMESTAMP']),
    'historical_faults': [],
    'runtime': common.runtime_fingerprints(),
    'packet_manifest_sha256': common.sha(packet / 'manifest.json'),
    'render_mapping': {p.name: str(p.resolve()) for p in sorted(Path('/dev/dri/by-path').glob('*-render'))},
    'retired_pids': [6955, 8318],
    'scope': 'One bounded discovery/copy/compute/peer-copy assessment; FAULT unchanged; no model admission or recovery actions',
    'active_probe_limit': 1, 'minimum_quiet_seconds': 60, 'native_worker_timeout_seconds': 60,
    'previous_boot_id': 'd9f2e066-f972-4f3b-bf44-ab47b922049f',
    'user_confirmed_restart': True,
    'user_words': 'the computer froze, fyi, so i just restarted it (2026-09-17, after the 2026-09-16 23:27 UTC fault; host froze 00:10 UTC)',
    'expected_devices': faulted['devices'],
    'priority3_prefix_lines': [r['MESSAGE'] for r in records if int(r['PRIORITY']) <= 3],
}
with (OUT / 'admission.json').open('x') as h:
    h.write(json.dumps(admission, indent=2) + '\n')
with (OUT / 'journal-baseline.jsonl').open('x') as h:
    h.write(raw)
print(json.dumps({'admission_sha256': common.sha(OUT / 'admission.json'), 'records': len(records),
                  'priority3': len(admission['priority3_prefix_lines'])}))
