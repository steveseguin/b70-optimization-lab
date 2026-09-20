#!/usr/bin/env python3
"""Write a same-boot health admission after a GPU fault that the sealed launcher now refuses.

Metadata only. Unlike the external-boot admissions, the fault records are part of
this boot's kernel prefix; the admission pins the complete prefix (which
contains them) so the health check and the launcher can require that no NEW
fault record appears after it. There may be no FAULT.json when the faulting
process died before its watcher latched; that is recorded rather than required.
Usage: prepare-same-boot-admission.py <tag> <packet-name> <retired pids...>
"""
import datetime, hashlib, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / 'scripts'))
import encoder_runtime_common as common
from serve_encoder_fault import FAULT   # the launcher's own detector regex

tag, packet_name, *pids = sys.argv[1:]
FIELDS = ('__CURSOR', '_BOOT_ID', '__MONOTONIC_TIMESTAMP', '__REALTIME_TIMESTAMP', 'MESSAGE', 'PRIORITY')
OUT = LANE / f'data/same-boot-admission-{tag}'
OUT.mkdir(exist_ok=False)
canonical = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
raw = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', '-o', 'json'], text=True, timeout=10)
records = [{k: r[k] for k in FIELDS} for r in map(json.loads, raw.splitlines())]
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert all(r['_BOOT_ID'] == boot.replace('-', '') for r in records)
known_faults = [r for r in records if FAULT.search(r['MESSAGE'])]
faulted = json.loads(sorted((common.ROOT).glob('encoder-server-*/server-identity.json'), key=lambda p: p.stat().st_mtime)[-1].read_text())
fault_file = common.ROOT / 'FAULT.json'
admission = {
    'schema': 'ltx.same-boot-health-admission.v1',
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'boot_id': boot,
    'fault_sha256': common.sha(fault_file) if fault_file.exists() else None,
    'journal_prefix_count': len(records),
    'journal_prefix_sha256': canonical(records),
    'journal_last_monotonic_us': int(records[-1]['__MONOTONIC_TIMESTAMP']),
    'known_fault_records': [{'cursor': r['__CURSOR'], 'message': r['MESSAGE']} for r in known_faults],
    'known_fault_count': len(known_faults),
    'runtime': common.runtime_fingerprints(),
    'packet_manifest_sha256': common.sha(common.ROOT / packet_name / 'manifest.json'),
    'render_mapping': {p.name: str(p.resolve()) for p in sorted(Path('/dev/dri/by-path').glob('*-render'))},
    'retired_pids': [int(p) for p in pids],
    'scope': 'One bounded discovery/copy/compute/peer-copy assessment on the SAME boot after a process-level GPU fault; the known fault records are pinned inside the prefix; no reset, no model admission by itself',
    'active_probe_limit': 1, 'minimum_quiet_seconds': 60, 'native_worker_timeout_seconds': 60,
    'expected_devices': faulted['devices'],
    'priority3_prefix_lines': [r['MESSAGE'] for r in records if int(r['PRIORITY']) <= 3],
}
with (OUT / 'admission.json').open('x') as h:
    h.write(json.dumps(admission, indent=2) + '\n')
import gzip
with gzip.open(OUT / 'journal-baseline.jsonl.gz', 'wt') as h:
    h.write(raw)
print(json.dumps({'admission_sha256': common.sha(OUT / 'admission.json'), 'records': len(records),
                  'known_faults': len(known_faults), 'fault_json_present': fault_file.exists()}))
