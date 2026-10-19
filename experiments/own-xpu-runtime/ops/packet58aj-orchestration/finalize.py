"""Last content writes: CPU-ready proposals and a conditionally prepared chain."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

O = Path(__file__).resolve().parent
R = O.parents[3]
P = R / 'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'


def read(p):
    return json.loads(p.read_text())


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, stdin=subprocess.DEVNULL).strip()
    remote = subprocess.check_output(['git', 'rev-parse', 'origin/main'], text=True, stdin=subprocess.DEVNULL).strip()
    assert head == remote, 'push preparation first'
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--', str(P), str(O)], text=True, stdin=subprocess.DEVNULL).strip(), 'commit owned preparation first'
    checks = read(O / 'final-checks.json')
    assert checks['passed']
    subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'], check=True, stdin=subprocess.DEVNULL)
    ready = read(P / 'ready.json')
    assert not ready['ready'] and 'smoke/v5 pending' in ready['reason']
    for name in ('evidence/card0-58aj-a', 'screen/evidence/card0-58ajb-screen-a', 'evidence/fault-review-58aj-a.json', 'READY-FOR-DEVICE.json'):
        assert not (P / name).exists(), name
    assert not (O / 'READY-FOR-DEVICE.json').exists()
    files = [P / name for name in (
        'build-receipt.json', 'submission-pins.json', 'ready.json',
        'runtime-selection.json', 'readiness-policy.json', 'submission-policy.json',
        'record-threshold.snapshot', 'WINDOW.md', 'MEMORY.md',
        'evidence/plan-check.json', 'evidence/queue-plans.json',
        'evidence/packet58ajb-preparation.json')]
    proposals = [R / 'experiments/own-xpu-runtime/ops/lane-queue' / f'proposed-p58aj-{tag}-A.txt' for tag in ('smoke', 'v5')]
    common = dict(
        schema='packet58aj.ready-for-device.v1', packet=P.name,
        prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        preparation_commit=head, preparation_passed=True, passed=True,
        revision='packet58ajb', wait_seconds=300,
        prior_failed_smoke='screen/evidence/card0-58aj-screen-a/smoke',
        failed_event_identity='not recorded; first-prefill timeout; root cause remains unproven',
        local_device_define_preparation_passed=True, shared_preparation_adapter_status='WARN: unsupported unranked one-card argv and private RoPE access',
        ready_for_coordinator_check=True, ready_for_device_chain=False,
        device_quality_pending=True, device_performance_pending=True,
        runtime_readiness_passed_at_preparation=False,
        files_sha256={str(f.relative_to(R)): sha(f) for f in files + proposals},
        final_checks_content_digest=sha(O / 'final-checks.json'),
        finalizer_content_digest=sha(Path(__file__)),
        # Historical window receipts carry old relative build paths. Bind the
        # diagnosis bytes without admitting that incident as a live pin closure.
        diagnosis_content_digest=sha(P / 'evidence/packet58ajb-diagnosis.json'),
        orchestration_provenance_only=str(O.relative_to(R)),
        work_note_provenance_only='notes/2026-10-19-own-runtime-packet58aj.md',
        lane='A', card=0, scope='whole-host',
        coordinator_prerequisites=['p153 lane-B run complete', 'p151 lane-B run complete', 'both lanes paused and drained'],
        chain_unit='packet58-onecard-58aj-a', chain_command=ready['chain_command'],
        chain_command_digest_sha256=hashlib.sha256(ready['chain_command'].encode()).hexdigest(),
        chain_output=str((P / 'evidence/card0-58aj-a').relative_to(R)),
        fault_review=str((P / 'evidence/fault-review-58aj-a.json').relative_to(R)),
        chain_gate='Recompute verify_ready.py after exact own smoke and five-view warm neutrality within inclusive +/-0.5%; ready=true required.',
        codex_frozen_from='WS', codex_frozen_through='WS128 completion',
        whole_host_hold_required_through_gaps=True,
        configuration=read(P / 'runtime-selection.json'),
        pinned_predecessor=read(P / 'submission-policy.json')['supersedes'],
        host_required_available_bytes=98_990_252_032, host_reserve_bytes=8 * 1024**3,
        preparation_disk_floor_bytes=27_000_000_000, device_disk_floor_bytes=25_000_000_000,
        storage_admission_pending_at_launch=True,
        strict512_claim=False, fresh_timing_repeat_passed=False,
        prior_58ah_attempts_disclosed=['a: 30.050 tok/s, not submitted; 3736 vs 124 major faults',
            'b: 31.66271941826957 tok/s, submitted cmvekebvh00a0rf01q3v2c3cz; 24 vs 2079 major faults'],
        no_retry=True, queued=False, device_executed=False, services_started=False,
        model_payload_reads=False, live_queue_changed=False, submission_performed=False,
        final_content_write=True)
    # These are the final content writes. Only read-only checks and Git follow.
    (P / 'READY-FOR-DEVICE.json').write_text(json.dumps(dict(common,
        ready_for_device=True, readiness_scope='CPU-qualified smoke and v5 proposals; fresh coordinator admission required'), indent=2) + '\n')
    (O / 'READY-FOR-DEVICE.json').write_text(json.dumps(dict(common,
        ready_for_device=True, readiness_scope='CPU-qualified smoke and v5 proposals; seven-window chain still requires own smoke and v5 device qualification'), indent=2) + '\n')
    print('Final packet and conditional chain markers written for ' + head)


if __name__ == '__main__':
    main()
