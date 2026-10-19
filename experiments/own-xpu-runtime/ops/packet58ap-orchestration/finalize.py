"""Write READY last; preparation success never substitutes for v5 qualification."""
import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain'
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert not (P/'READY-FOR-DEVICE.json').exists() and not (O/'READY-FOR-DEVICE.json').exists()
    assert not (P/'evidence/card0-58ap-a').exists() and not (P/'evidence/fault-review-58ap-a.json').exists()
    subprocess.run([sys.executable,'-B',str(P/'seal.py'),'--verify'],stdin=subprocess.DEVNULL,check=True)
    ready=read(P/'ready.json');entry=read(O/'entry-report.json');cpu=read(P/'evidence/cpu-sequence.json')
    assert entry['passed'] and all(j['report']['passed'] for j in entry['jobs'])
    assert cpu['passed'] and cpu['device_executed'] is False and cpu['peak_child_rss_bytes']<4*1024**3
    assert len(cpu['records'])==7 and all(r['passed'] and r['memory_sensors']['passed'] for r in cpu['records'])
    assert read(P/'evidence/python-cpu-gates.json')['passed']
    submission=read(P/'evidence/submission-rehearsal.json');assert submission['passed'] and submission['final_location_cli_passed'] and not submission['network_used']
    paths=[P/n for n in ('build-receipt.json','submission-pins.json','ready.json','parent-binding.json','native-artifacts.json','WINDOW.md','RELEASE-AMENDMENT.md','evidence/argument-gate.json','evidence/cpu-sequence.json','evidence/python-cpu-gates.json','evidence/submission-rehearsal.json','evidence/plan-check.json','evidence/storage-plan.json')]
    paths += [O/n for n in ('entry-report.json','entry-proposal.jsonl','finalize.py')]
    condition=ready['release_condition'];is_ready=ready['ready'] is True
    row=dict(schema='packet58ap.ready-for-device.v1',packet=P.name,prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_commit=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip(),
        preparation_passed=True,passed=True,ready_for_device=is_ready,ready_for_device_chain=is_ready,ready_for_coordinator_check=True,parent_qualification_required_at_launch=True,release_condition=condition,release_status=ready.get('reason','v5 passed at preparation; recompute at launch'),
        coordinator_unit='packet58-onecard-58ap-a',chain_unit='packet58-onecard-58ap-a',chain_output=str((P/'evidence/card0-58ap-a').relative_to(ROOT)),fault_review=str((P/'evidence/fault-review-58ap-a.json').relative_to(ROOT)),chain_command=ready['chain_command'],chain_command_digest_sha256=hashlib.sha256(ready['chain_command'].encode()).hexdigest(),command_hash_encoding='UTF-8, no trailing newline',
        windows=['K1a','K1b','KD','W2m','WS','WS128x','WS128'],gap_seconds=90,wait_seconds=300,lane='A',card=0,scope='whole-host',configuration=read(P/'runtime-selection.json'),
        whole_host_hold_required_through_gaps=True,both_lanes_pause_and_drain_required=True,codex_frozen_from='WS',codex_frozen_through='WS128 completion',
        v5_proposal='experiments/own-xpu-runtime/ops/lane-queue/proposed-p58am-v5-A.txt',v5_output_resolved_at_launch=True,readiness_policy=read(P/'readiness-policy.json'),bracket_rates_tok_s=ready.get('rates'),
        pinned_predecessor=read(P/'submission-policy.json')['supersedes'],submission_requires_above_pinned_and_live_record=True,submission_scope_tokens=128,strict512_claim=False,fresh_timing_repeat_passed=False,
        submission_rehearsal_passed=True,shared_entry_report_passed=True,shared_preparation_adapter_status='WARN: unranked one-card ABI has no shared preparation adapter. Seven actual native CPU probes and supplemental demand resets pass independently.',python_tests=read(P/'evidence/python-cpu-gates.json')['tests'],peak_child_rss_bytes=cpu['peak_child_rss_bytes'],preparation_ram_budget_bytes=4*1024**3,
        files_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},native_artifacts=read(P/'build-receipt.json')['artifacts'],candidate_sources_vendored=True,candidate_binary_vendored=True,candidate_recompiled=False,k1_adapter_only_compiled=True,
        chain_quality_pending=True,chain_performance_pending=True,no_retry=True,queued=False,device_executed=False,services_started=False,model_payload_reads=False,live_queue_changed=False,submission_performed=False,final_content_write=True)
    # These are the final content writes. Only read-only checks and Git follow.
    for dest in (P/'READY-FOR-DEVICE.json',O/'READY-FOR-DEVICE.json'):dest.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(preparation_passed=True,ready_for_device=is_ready,release_condition=condition)))
if __name__=='__main__':main()
