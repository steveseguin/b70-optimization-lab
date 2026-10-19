"""Write packet58ahb's final marker after its preparation commit is pushed."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

O = Path(__file__).resolve().parent
R = O.parents[3]
P = R / 'experiments/own-xpu-runtime/stage2/packet58ah-onecard-record'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    ready = read(P / 'ready.json')
    checks = read(O / '58ahb-light-gates.json')
    assert checks['passed'] and ready['ready']
    assert not (P / 'evidence/card0-58ah-b').exists()
    assert not (P / 'evidence/fault-review-58ah-b.json').exists()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R,
                                    text=True, stdin=subprocess.DEVNULL).strip()
    remote = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=R,
                                    text=True, stdin=subprocess.DEVNULL).strip()
    assert commit == remote, 'push preparation before final marker'
    subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'],
                   check=True, stdin=subprocess.DEVNULL)
    command = ready['chain_command']
    old = read(P / 'lineage/58ah-chain-a-ready.json')['chain_command']
    assert command == old.replace('packet58-onecard-58ah-a', 'packet58-onecard-58ah-b').replace(
        'card0-58ah-a', 'card0-58ah-b').replace('fault-review-58ah-a.json', 'fault-review-58ah-b.json')
    assert hashlib.sha256(command.encode()).hexdigest() == checks['chain_command_sha256']
    sys.path.insert(0, str(P))
    import packet58_submission as S
    names = ['build-receipt.json', 'submission-pins.json', 'ready.json',
             'runtime-selection.json', 'readiness-policy.json', 'submission-policy.json',
             'record-threshold.snapshot', 'WINDOW.md', 'parent-binding.json',
             'evidence/argument-gate.json', 'evidence/python-cpu-gates.json',
             'evidence/submission-rehearsal.json', 'evidence/plan-check.json',
             'lineage/58ah-chain-a-build-receipt.json',
             'lineage/58ah-chain-a-submission-pins.json',
             'lineage/58ah-chain-a-ready.json', 'lineage/58ah-chain-a-READY-FOR-DEVICE.json']
    files = [P / n for n in names] + [O / n for n in (
        '58ahb-light-gates.json', '58ahb-readiness.log', '58ahb-external-pins.json',
        '58ahb-chain-a-inventory.json', 'finalize_chain_b.py')]
    row = dict(
        schema='packet58ah.ready-for-device.v1', packet=P.name, amendment='packet58ahb',
        prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        commit_sha=commit, commit_scope='Pushed chain-b preparation; final marker committed separately.',
        preparation_passed=True, ready_for_coordinator_check=True,
        ready_for_device=True, ready_for_device_chain=True,
        runtime_readiness_passed_at_preparation=True, parent_qualification_required_at_launch=True,
        chain_attempt='b', coordinator_unit='packet58-onecard-58ah-b',
        chain_output=str((P / 'evidence/card0-58ah-b').relative_to(R)),
        fault_review=str((P / 'evidence/fault-review-58ah-b.json').relative_to(R)),
        chain_command=command, chain_command_digest_sha256=checks['chain_command_sha256'],
        command_hash_encoding='UTF-8 chain_command bytes, no trailing newline',
        command_changes=['coordinator unit', 'chain output', 'fresh fault-review path required by WINDOW.md'],
        files_sha256={str(f.relative_to(R)): sha(f) for f in files},
        native_artifacts=read(P / 'build-receipt.json')['artifacts'],
        configuration=read(P / 'runtime-selection.json'),
        pinned_predecessor=read(P / 'submission-policy.json')['supersedes'],
        readiness_policy=read(P / 'readiness-policy.json'),
        parent_smoke_observed_passed=ready['smoke_passed'],
        parent_v5_observed_complete=True, control_drift=ready['control_drift'],
        minimum_gain=ready['minimum_gain'], projection_is_measurement=False,
        python_tests=checks['python_tests'], actual_entries=7,
        wrong_unit_environment_refusals=28, submission_rehearsal_passed=True,
        submission_cli_root_overridden=False, preparation_peak_rss_bytes=checks['peak_rss_bytes'],
        preparation_ram_budget_bytes=2_000_000_000,
        prior_chain=dict(attempt='a', ws128_tok_s=30.050, submitted=False,
                        ws128_major_faults=3736, ws128x_major_faults=124,
                        reason='CPU work may have disturbed host paging; unproven.',
                        evidence_immutable=True,
                        original_marker='lineage/58ah-chain-a-READY-FOR-DEVICE.json',
                        preregistration='notes/2026-10-19-own-runtime-packet58ah-chain-a-result.md'),
        rerun_disclosure=S.RERUN_DISCLOSURE, final_attempt=True, no_third_run=True,
        no_selection_between_attempts=True, submission_requires_above_pinned_record=True,
        submission_discloses_chain_a=True, whole_host_hold_required_through_gaps=True,
        both_lanes_pause_and_drain_required=True,
        all_codex_units_frozen_from_before_K1a_until_completion=True,
        codex_frozen_from='before K1a', codex_frozen_through='WS128 completion',
        compiles_blocked_throughout=True, other_model_reading_cpu_work_excluded=True,
        cache_drops_settings_and_pretouch_forbidden=True,
        generic_waiter_only_freezes_at_WS=True,
        coordinator_must_arrange_before_K1a_freeze=True,
        coordinator_requirements_performed_by_preparer=False,
        submission_scope_tokens=128, strict512_claim=False, fresh_timing_repeat_passed=False,
        native_recompiled=False, native_binaries_executed=False,
        native_fullshape_gates_rerun=False, model_payload_reads=False,
        launch_performed=False, device_executed=False, services_started=False,
        live_queue_changed=False, submission_performed=False, chain_b_output_created=False,
        chain_a_evidence_modified=False, final_content_write=True)
    # LAST repository content write. Only read-only checks and Git follow.
    (O / 'READY-FOR-DEVICE.json').write_text(json.dumps(row, indent=2) + '\n')
    print('Final chain-b marker written for ' + commit)


if __name__ == '__main__':
    main()
