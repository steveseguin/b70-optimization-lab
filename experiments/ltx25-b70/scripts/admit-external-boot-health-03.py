#!/usr/bin/env python3
"""One root-reviewed archival of the old-boot fault; no native execution."""
import datetime
import fcntl
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / 'scripts'))
spec = importlib.util.spec_from_file_location('health_review', LANE / 'scripts/check-external-boot-health-03.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.common.sha(Path(m.__file__)) == '2e72ea510bb54ad83754badaa7290974c1be49b32a69107b178a56d3ee77e1d6'

handles = []
for name in m.LOCKS:
    handle = open(name, 'a')
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    handles.append(handle)
a = m.identity()  # Requires original venv metadata; never imports Torch.
out = m.OUT
parent = json.loads((out / 'result.json').read_text())
worker = json.loads((out / 'worker-result.json').read_text())
assert parent['status'] == 'limited-health-assessment-passed'
assert parent['worker_exit_code'] == 0 and parent['native_children'] == 1
assert worker['status'] == 'passed' and worker['strict_determinism'] and not worker['warn_only']
assert parent['worker_pid'] == worker['pid']
assert parent['admission_sha256'] == m.ADMISSION_SHA and parent['boot_id'] == a['boot_id']
assert worker['devices'] == a['expected_devices']
assert len(worker['peer_copies']) == 12
assert {(x['source'], x['target']) for x in worker['peer_copies']} == {(i, j) for i in range(4) for j in range(4) if i != j}
assert all(x['exact'] and x['bytes'] == 131072 and x['dtype'] == 'bfloat16' for x in worker['peer_copies'])
assert not any(Path('/proc', str(pid)).exists() for pid in (parent['pid'], worker['pid']))
assert parent['source_sha256'] == m.common.sha(Path(m.__file__))
passive = m.passive(a, 'root-reviewed')
fault = m.common.ROOT / 'FAULT.json'
old = fault.read_bytes()
historical = out / 'historical-FAULT.json'
assert not historical.exists()
with historical.open('xb') as stream:
    stream.write(old)
assert hashlib.sha256(historical.read_bytes()).hexdigest() == a['fault_sha256']
intent = {
    'schema': 'ltx.external-boot-recovery-admission.v2',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'boot_id': a['boot_id'], 'previous_boot_id': a['previous_boot_id'],
    'user_confirmed_restart': True, 'agent_rebooted': False,
    'source_sha256': parent['source_sha256'],
    'archival_script_sha256': m.common.sha(Path(__file__)),
    'health_result_sha256': m.common.sha(out / 'result.json'),
    'worker_result_sha256': m.common.sha(out / 'worker-result.json'),
    'historical_fault_sha256': a['fault_sha256'], 'passive': passive,
    'decision': 'Archive old-boot hold after root review of successful bounded health assessment and released processes/devices; admit the packet 61 upsampler-gate campaign next, one launch, no restart chain',
    'model_service_started': False, 'model_transition_or_speed_qualified': False,
    'reset_or_host_settings_changes': False,
    'future_fault_rule': 'New fault halts new requests; no retry or restart chain',
}
m.write(out / 'recovery-admission.json', intent)
assert fault.read_bytes() == old
fault.unlink()
m.write(out / 'fault-archive-completed.json', {
    'historical_fault_sha256': m.common.sha(historical),
    'root_fault_absent': not fault.exists(),
    'recovery_admission_sha256': m.common.sha(out / 'recovery-admission.json'),
})
repo = LANE / 'data/external-boot-health-03'
for name in ('result.json', 'worker-result.json', 'started.json', 'worker-started.json',
             'worker.log', 'historical-FAULT.json', 'recovery-admission.json', 'fault-archive-completed.json'):
    with (repo / name).open('xb') as stream:
        stream.write((out / name).read_bytes())
logs = {p.name: p.read_text() for p in sorted(out.glob('*journal.jsonl'))}
with (repo / 'native-journals.json.gz').open('xb') as stream:
    stream.write(gzip.compress(json.dumps(logs, sort_keys=True).encode(), mtime=0))
print(json.dumps({'health_passed': True, 'root_fault_archived': not fault.exists(),
                  'boot_id': a['boot_id'], 'root_admission': str(out / 'recovery-admission.json')}))
