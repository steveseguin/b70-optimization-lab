"""Write the final preparation handoff after checks and the preparation push."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys
R=Path(__file__).resolve().parents[4]
P=R/'experiments/own-xpu-runtime/stage2/packet58ad-onecard-record'
O=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    ready=read(P/'ready.json');binding=read(P/'parent-binding.json')
    assert not (P/'evidence/card0-58ad-a').exists()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True,stdin=subprocess.DEVNULL).strip()
    remote=subprocess.check_output(['git','rev-parse','origin/main'],cwd=R,text=True,stdin=subprocess.DEVNULL).strip()
    assert commit==remote,'push preparation before final marker'
    sys.path.insert(0,str(P))
    import window
    window.build_gate()
    validation=read(O/'validation.json');assert validation['passed']
    sys.path.insert(0,str(R/'experiments/own-xpu-runtime/ops/lane-queue'))
    import pin_guard
    assert pin_guard.check_job(read(O/'entry-proposal.jsonl'))['passed']
    command=ready['chain_command']
    names=['build-receipt.json','submission-pins.json','runtime-selection.json','readiness-policy.json',
        'submission-policy.json','record-threshold.snapshot','WINDOW.md','parent-binding.json',
        'evidence/argument-gate.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json',
        'evidence/native-entry.json','evidence/plan-check.json']
    row=dict(schema='packet58ad.ready-for-device.v1',packet='packet58ad-onecard-record',
        prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        commit_sha=commit,commit_scope='Pushed preparation; final marker committed separately.',
        chain_command=command,chain_command_digest_sha256=hashlib.sha256(command.encode()).hexdigest(),
        command_hash_encoding='UTF-8 chain_command bytes, no trailing newline',
        files_sha256={str((P/n).relative_to(R)):sha(P/n) for n in names},
        coordinator_unit='packet58-onecard-58ad-a',chain_output=str((P/'evidence/card0-58ad-a').relative_to(R)),
        preparation_passed=True,ready_for_coordinator_check=True,
        ready_for_device_chain=ready['ready'],runtime_readiness_passed_at_preparation=ready['ready'],
        runtime_readiness_reason=ready.get('reason'),parent_qualification_required_at_launch=True,
        parent_build_sha256=binding['parent_build_sha256'],parent_ready_sha256=binding['parent_ready_sha256'],
        parent_ready_for_device_at_binding=binding['parent_ready_for_device_at_binding'],
        configuration=read(P/'runtime-selection.json'),pinned_predecessor=read(P/'submission-policy.json')['supersedes'],
        readiness_policy=read(P/'readiness-policy.json'),projection_is_measurement=False,
        python_tests=read(P/'evidence/python-cpu-gates.json')['tests'],actual_entries=7,
        wrong_unit_environment_refusals=28,native_entry_rehearsal_passed=True,pin_guard_passed=True,
        submission_rehearsal_passed=True,submission_cli_root_overridden=False,native_recompiled=False,
        native_fullshape_gates_rerun=False,model_payload_reads=False,preparation_ram_ceiling_bytes=4*1024**3,
        same_uninterrupted_hold_as_58ab_smoke_and_v5_required=True,whole_host_hold_required_through_gaps=True,
        lane_b_pause_and_drain_required=True,codex_frozen_from='WS',codex_frozen_through='WS128 completion',
        compiles_blocked_from_WS=True,submission_scope_tokens=128,strict512_claim=False,
        fresh_timing_repeat_passed=False,launch_performed=False,device_executed=False,
        services_started=False,live_queue_changed=False,submission_performed=False,final_content_write=True)
    # Deliberately the last content write; no evidence or notes are written after this.
    (O/'READY-FOR-DEVICE.json').write_text(json.dumps(row,indent=2)+'\n')
    print('READY-FOR-DEVICE.json written for '+commit+'; device gate '+str(ready['ready']))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
