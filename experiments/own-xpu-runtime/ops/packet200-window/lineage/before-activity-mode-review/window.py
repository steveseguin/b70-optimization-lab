"""Non-operational packet200 window contract scaffold.

No service/queue/latch/worker command is executed or imported here. The sealed
packet199 topology is retained by hash for a later separately reviewed adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKET = ROOT / 'experiments/own-xpu-runtime/stage2/packet200-bounded-serving'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
UNIT = 'packet200-bounded-serving-a'
OPERATIONAL_ENTRYPOINT_ENABLED = False
SAFE_PROPERTIES = dict(Restart='no', SendSIGKILL='no', TimeoutStopSec='infinity',
                       KillMode='process', ExitType='cgroup')
PHASES = ('read-only admission and endpoint-idle proof', 'record endpoint and latch identities',
          'one graceful endpoint stop', 'passive privileged preflight drain',
          'revalidate closure/memory/storage/fault review', 'locked PAUSE-A handoff',
          'one worker unit', 'fault/STOP/worker monitoring', 'rearm exact PAUSE-A',
          'terminal runtime+evidence+unit proof', 'passive privileged postflight drain',
          'one guarded restoration of prior endpoints')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def verify_topology():
    pins = json.loads((HERE / 'helper-pins.json').read_text())
    require(pins['operational_entrypoint_enabled'] is False, 'operational scaffolding claim changed')
    for name, expected in pins['files_sha256'].items():
        require(sha(ROOT / name) == expected, 'frozen topology source changed: ' + name)
    return pins


def staging_identity(parent):
    parent = Path(parent)
    require(parent.is_absolute() and parent.is_relative_to(ROOT) and parent.resolve() == parent,
            'real repository-local staging parent required')
    state = parent.lstat()
    require(stat.S_ISDIR(state.st_mode) and state.st_uid == os.getuid() and
            stat.S_IMODE(state.st_mode) == 0o700 and state.st_dev == ROOT.stat().st_dev,
            'staging parent must be private0700 on local filesystem')
    require(not any(os.path.lexists(parent / child) for child in ('output','checkpoints')),
            'fresh output/checkpoint children required; no retry')
    return dict(path=str(parent), device=state.st_dev, inode=state.st_ino,
                uid=state.st_uid, mode='0700')


def validate_cpu_plan(plan, parent):
    """Read-only contract/source checks; does not call the worker or admit live work."""
    stage = staging_identity(parent)
    parent = Path(stage['path'])
    require(plan.get('schema') == 'packet200.bounded-serving-plan.v1' and plan.get('passed') is True
            and plan.get('device_executed') is False and plan.get('live_admission_ready') is False,
            'CPU-only worker plan required')
    require(plan.get('storage_admission_mode') == 'monitored-forecast' and plan.get('storage_bound_proven') is False,
            'forecast cannot become a proven bound')
    require(plan.get('unit') == UNIT and type(plan.get('native_processes')) is int and plan['native_processes'] == 1,
            'one fixed worker/owner required')
    require(plan.get('activity_mode') in ('launch','mapped-cold-start'), 'unknown activity provenance mode')
    require(plan.get('terminal_receipt') == str(parent/'output/terminal/worker.json'), 'terminal path differs')
    require(plan.get('bind_host') == '127.0.0.1' and type(plan.get('bind_port')) is int and plan['bind_port'] == 0,
            'ephemeral loopback listener required')
    profile = plan['profile']
    require(plan.get('profile_sha256') == digest(profile), 'profile digest differs')
    require(profile.get('live_admission_ready') is False and profile.get('submission_eligible') is False,
            'experimental profile scope changed')
    require(profile['paths'] == dict(output=str(parent/'output'), owner_output=str(parent/'output/owner'),
                                     checkpoint_root=str(parent/'checkpoints')), 'private child paths differ')
    expected = dict(requests=16, context=4096, max_new=512, parking_bytes=512*1024**2,
        save_bound_bytes=256*1024**2, planned_write_bytes=768*1024**2, disk_floor_bytes=27_000_000_000,
        host_required_available_bytes=98_990_252_032, coordinator_margin_bytes=1024**3)
    require(all(type(profile['limits'].get(k)) is int and profile['limits'][k] == v for k,v in expected.items()),
            'registered memory/storage/request limits differ')
    require(plan.get('native_cpu_affinity') == [0,1,2,3,16,17,18,19] and plan.get('native_nice') == 0,
            'native placement differs')
    require(plan.get('helper_cpu_affinity') == list(range(8,16))+list(range(24,32)) and plan.get('helper_nice') == 19,
            'helper placement differs')
    sources = dict(profile['source_sha256'])
    for name, value in plan['source_sha256'].items():
        require(sources.get(name,value) == value, 'conflicting source closure')
        sources[name] = value
    require(bool(sources), 'empty source closure')
    for name, value in sources.items():
        path = ROOT / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and path.resolve().is_relative_to(ROOT),
                'source outside repository')
        require(sha(path) == value, 'worker/profile source changed: ' + name)
    return dict(passed=True, read_only=True, live_admission_ready=False, operational_entrypoint_enabled=False,
                staging_identity=stage, plan_sha256=digest(plan), source_files=len(sources),
                topology=list(PHASES), safe_properties=dict(SAFE_PROPERTIES))


def require_same_staging_identity(previous):
    require(staging_identity(previous['path']) == previous, 'staging parent identity changed during admission')


def future_worker_argv(plan, fault_review):
    """Describe the proposed future CLI only; current worker accepts --plan only."""
    parent = Path(plan['profile']['paths']['output']).parent
    return [PYTHON, '-B', str(PACKET/'device_worker.py'), '--authorized-device-window',
            '--staging-parent', str(parent), '--fault-review', str(fault_review),
            '--output', str(parent/'output')]


def validate_terminal(row, *, plan_sha256, unit_status, passive_drained):
    """Pure restore prerequisite check; returning success performs no restoration."""
    require(unit_status.get('ActiveState') == 'inactive' and unit_status.get('Result') == 'success'
            and unit_status.get('ExecMainStatus') == '0', 'worker unit must exit successfully')
    require(passive_drained is True, 'separate passive whole-host drain required')
    expected = dict(passed=True, runtime_passed=True, evidence_passed=True, owner_exited=True,
        diagnostics_finished=True, devices_drained=True, retained=False, model_loads=1,
        native_process_count=1, incident_sigterm_count=0, owner_returncode=0,
        store_closed=True, writers_closed=True, coordination_completed=True)
    require(all(type(row.get(k)) is type(v) and row[k] == v for k,v in expected.items()),
            'runtime/evidence/ownership completion failed')
    require(row.get('plan_sha256') == plan_sha256, 'terminal plan identity differs')
    require(row.get('storage_admission_mode') == 'monitored-forecast' and row.get('storage_bound_proven') is False
            and row.get('live_profile_ready') is False, 'terminal scope changed')
    require('error' not in row, 'terminal incident evidence remains')
    count = row.get('requests')
    require(type(count) is int and 0 <= count <= 16 and type(row.get('controls')) is int
            and row['controls'] == count, 'interactive request/control counts differ')
    stopped = row.get('stopped', {})
    stop_fields = dict(event='stopped',safe_to_exit=True,completed_requests=count,completed_controls=count,
                       discarded_pending=False,pending_request_id='')
    require(all(type(stopped.get(k)) is type(v) and stopped[k] == v for k,v in stop_fields.items()),
            'clean native disposition proof required')
    require(stopped.get('reason') in ('quit','idle-timeout','deadline','request-limit'),
            'incident signal/EOF cannot become normal closure')
    diagnostics = row.get('diagnostics', {})
    require(diagnostics.get('eof') is True and all(diagnostics.get(k) is False for k in
            ('retained','reader_retained','capture_retained','owned_read_fd_open','reader_startup_uncertain','incident')),
            'diagnostic EOF and resource release required')
    return dict(passed=True, completed_requests=count, lifecycle_only=count == 0,
                restoration_performed=False, operational_entrypoint_enabled=False)


if __name__ == '__main__':
    raise SystemExit('CPU contract scaffold only; no operational CLI or launch authorization')
