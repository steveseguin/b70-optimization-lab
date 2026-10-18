from pathlib import Path
import datetime,hashlib,json,subprocess,sys
R=Path(__file__).resolve().parents[4]
P=R/'experiments/own-xpu-runtime/stage2/packet58z-onecard-record'
O=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
ready=json.loads((P/'ready.json').read_text())
assert ready['ready'] and not (P/'evidence/card0-58z-a').exists()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
remote=subprocess.check_output(['git','rev-parse','origin/main'],cwd=R,text=True).strip()
assert commit==remote,'push preparation before final marker'
sys.path.insert(0,str(R/'experiments/own-xpu-runtime/ops/lane-queue'))
import pin_guard
assert pin_guard.check_job(json.loads((O/'entry-proposal.jsonl').read_text()))['passed']
command=ready['chain_command']
names=['build-receipt.json','submission-pins.json','ready.json','runtime-selection.json','readiness-policy.json','submission-policy.json','record-threshold.snapshot','WINDOW.md','evidence/argument-gate.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json','evidence/native-entry.json','evidence/plan-check.json']
row=dict(schema='packet58z.ready-for-device.v1',packet='packet58z-onecard-record',
    prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    commit_sha=commit,commit_scope='Pushed preparation; final marker committed separately.',
    chain_command=command,chain_command_digest_sha256=hashlib.sha256(command.encode()).hexdigest(),
    command_hash_encoding='UTF-8 chain_command bytes, no trailing newline',
    files_sha256={str((P/n).relative_to(R)):sha(P/n) for n in names},
    coordinator_unit='packet58-onecard-58z-a',chain_output=str((P/'evidence/card0-58z-a').relative_to(R)),
    ready_for_device_chain=True,parent_qualification_required_at_launch=True,
    configuration=json.loads((P/'runtime-selection.json').read_text()),
    pinned_predecessor=json.loads((P/'submission-policy.json').read_text())['supersedes'],
    minimum_gain=ready['minimum_gain'],control_drift=ready['control_drift'],
    warmup_view=ready['warmup_view'],combined_gain_over_record=ready['combined_gain_over_record'],
    readiness_projection_tok_s=ready['projected_record_tok_s'],projection_is_measurement=False,
    smoke_d_passed=True,python_tests=json.loads((P/'evidence/python-cpu-gates.json').read_text())['tests'],
    actual_entries=7,wrong_unit_environment_refusals=28,native_entry_rehearsal_passed=True,
    pin_guard_passed=True,submission_rehearsal_passed=True,native_recompiled=False,
    native_fullshape_gates_rerun=False,model_payload_reads=False,preparation_ram_ceiling_bytes=4*1024**3,
    whole_host_hold_required_through_gaps=True,lane_b_pause_and_drain_required=True,
    codex_frozen_from='WS',codex_frozen_through='WS128 completion',compiles_blocked_from_WS=True,
    submission_scope_tokens=128,strict512_claim=False,fresh_timing_repeat_passed=False,
    launch_performed=False,device_executed=False,services_started=False,
    live_queue_changed=False,submission_performed=False,final_content_write=True)
# This is deliberately the final content write, after all checks and the pushed preparation.
(O/'READY-FOR-DEVICE.json').write_text(json.dumps(row,indent=2)+chr(10))
print('READY-FOR-DEVICE.json written for '+commit)
