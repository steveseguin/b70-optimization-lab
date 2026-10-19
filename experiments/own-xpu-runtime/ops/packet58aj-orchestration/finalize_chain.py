"""Write both chain READY markers last, after CPU-only evidence checks."""
import datetime,hashlib,json,os,resource,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert not (P/'READY-FOR-DEVICE.json').exists() and not (O/'READY-FOR-DEVICE.json').exists()
    assert not (P/'evidence/card0-58aj-a').exists()
    assert not (P/'evidence/fault-review-58aj-a.json').exists()
    subprocess.run([sys.executable,'-B',str(P/'seal.py'),'--verify'],stdin=subprocess.DEVNULL,check=True)
    ready=read(P/'ready.json');assert ready['ready'] and ready['passed']
    assert ready['build_receipt_sha256']==sha(P/'build-receipt.json')
    assert ready['submission_pins_sha256']==sha(P/'submission-pins.json')
    assert ready['resident_noninferior'] and not ready['original_candidate_beats_all_controls']
    assert read(P/'evidence/python-cpu-gates.json')['passed']
    rehearsal=read(P/'evidence/submission-rehearsal.json')
    assert rehearsal['passed'] and rehearsal['final_location_cli_passed'] and not rehearsal['network_used']
    assert rehearsal['peak_rss_bytes']<2_000_000_000
    entry=read(O/'58ajc-entry-rehearsal.json')
    assert entry['passed'] and all(j['report']['passed'] for j in entry['jobs'])
    files=[P/n for n in ('build-receipt.json','submission-pins.json','ready.json',
        'runtime-selection.json','readiness-policy.json','submission-policy.json',
        'record-threshold.snapshot','WINDOW.md','verify_ready.py','seal.py','fault_review.py',
        'evidence/python-cpu-gates.json','evidence/submission-rehearsal.json')]
    files += [O/n for n in ('58ajc-entry-rehearsal.json','58ajc-reseal.json',
                           'amend_readiness.py','finalize_chain.py','entry-proposal.jsonl')]
    row=dict(schema='packet58aj.ready-for-device.v1',packet=P.name,revision='packet58ajc',
        prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        preparation_passed=True,passed=True,ready_for_device=True,ready_for_device_chain=True,
        ready_for_coordinator_check=True,runtime_readiness_passed_at_preparation=True,
        parent_qualification_required_at_launch=True,
        coordinator_unit='packet58-onecard-58aj-a',chain_unit='packet58-onecard-58aj-a',
        chain_output=str((P/'evidence/card0-58aj-a').relative_to(ROOT)),
        fault_review=str((P/'evidence/fault-review-58aj-a.json').relative_to(ROOT)),
        chain_command=ready['chain_command'],
        chain_command_digest_sha256=hashlib.sha256(ready['chain_command'].encode()).hexdigest(),
        command_hash_encoding='UTF-8, no trailing newline',
        windows=['K1a','K1b','KD','W2m','WS','WS128x','WS128'],gap_seconds=90,wait_seconds=300,
        lane='A',card=0,scope='whole-host',configuration=read(P/'runtime-selection.json'),
        whole_host_hold_required_through_gaps=True,both_lanes_pause_and_drain_required=True,
        coordinator_prerequisites=['active packet58ai census complete','other admitted work complete','both lanes paused and drained','fresh fault review and current admission'],
        codex_frozen_from='WS',codex_frozen_through='WS128 completion',
        readiness_policy=read(P/'readiness-policy.json'),
        bracket_rates_tok_s=ready['rates'],control_drift_fraction=ready['control_drift_fraction'],
        minimum_gain=ready['minimum_gain'],original_candidate_beats_all_controls=False,
        pinned_predecessor=read(P/'submission-policy.json')['supersedes'],
        submission_requires_above_pinned_and_live_record=True,
        submission_scope_tokens=128,strict512_claim=False,fresh_timing_repeat_passed=False,
        submission_rehearsal_passed=True,shared_entry_report_passed=True,
        shared_preparation_adapter_status='WARN: no preparation probe declared; retained packet58ajb device-define CPU proof applies to unchanged native artifacts',
        python_tests=read(P/'evidence/python-cpu-gates.json')['tests'],
        preparation_ram_budget_bytes=2_000_000_000,
        files_sha256={str(f.relative_to(ROOT)):sha(f) for f in files},
        native_artifacts=read(P/'build-receipt.json')['artifacts'],
        readiness_scope='Completed exact smoke/v5 qualify the fresh seven-window resident chain under the disclosed post-result non-inferiority amendment.',
        chain_quality_pending=True,chain_performance_pending=True,
        no_retry=True,queued=False,device_executed=False,native_recompiled=False,
        services_started=False,model_payload_reads=False,live_queue_changed=False,
        submission_performed=False,final_content_write=True)
    # Final content writes: only read-only checks and Git may follow.
    for path in (P/'READY-FOR-DEVICE.json',O/'READY-FOR-DEVICE.json'):
        path.write_text(json.dumps(row,indent=2)+'\n')
    print('Both chain READY files written last')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000));main()
