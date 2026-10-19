"""Write both truthful READY markers last; no launch or queue mutation.

packet58asd: the chain binary is the one wait-policy rebuild; READY is true only
when verify_ready.py, the interface proof and every CPU gate pass.
"""
import datetime,hashlib,json,os,resource,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait'
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert not (P/'READY-FOR-DEVICE.json').exists() and not (O/'READY-FOR-DEVICE.json').exists()
 subprocess.run([sys.executable,'-B',str(P/'seal.py'),'--verify'],stdin=subprocess.DEVNULL,check=True)
 ready=read(P/'ready.json');abi=read(P/'evidence/chain-native-interface.json')
 assert ready['ready'] is True and abi['passed'] is True and abi['native_recompiled'] is True
 assert abi['binary_sha256']==sha(P/'build/device/own-rt-iq3')==ready['chain_binary_sha256']
 assert abi['bracket_binary_sha256']==ready['bracket_binary_sha256']==sha(P/'build/bracket/device/own-rt-iq3')
 assert abi['source_patch']['parent_digest']==ready['chain_interface_patch_sha256']==sha(P/'chain-interface.patch')
 checks=read(O/'chain-checks.json');assert checks['passed'] and checks['native_interface_passed'] is True and checks['chain_binary_sha256']==abi['binary_sha256']
 assert all(read(P/n)['passed'] for n in ('evidence/wait-policy.json','evidence/build.json','evidence/chain-cpu-exactness.json','evidence/native-parser.json','evidence/chain-flags.json'))
 assert read(P/'evidence/submission-rehearsal.json')['passed']
 assert read(P/'evidence/argument-gate.json')['passed']
 assert 'Ran 137 tests' in (O/'python-tests.log').read_text() and '\nOK\n' in (O/'python-tests.log').read_text()
 bracket=read(P/'screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json')
 assert bracket['candidate_beats_all_controls'] and bracket['request_count']==60
 files=[P/n for n in ('build-receipt.json','submission-pins.json','ready.json','WINDOW.md','runtime-selection.json','submission-policy.json','record-threshold.snapshot','evidence/chain-native-interface.json','evidence/submission-rehearsal.json','evidence/argument-gate.json','evidence/wait-policy.json','evidence/build.json','evidence/chain-cpu-exactness.json','evidence/native-parser.json','evidence/chain-flags.json','chain-interface.patch')]
 files += [O/n for n in ('chain-checks.json','queue-plan.log','python-tests.log','check_chain.py','check_native_interface.py','close_screen_identity_asd.py','finalize_chain.py','entry-proposal.jsonl','arguments.log','submission-rehearsal.log')]
 row=dict(schema='packet58as.ready-for-device.v1',packet=P.name,revision='packet58asd',prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),preparation_passed=True,passed=True,ready_for_device=True,ready_for_device_chain=True,ready_for_coordinator_check=True,reason=abi['reason'],chain_binary_sha256=abi['binary_sha256'],bracket_binary_sha256=abi['bracket_binary_sha256'],chain_interface_patch_sha256=abi['source_patch']['parent_digest'],coordinator_unit='packet58-onecard-58as-a',chain_unit='packet58-onecard-58as-a',chain_output=str((P/'evidence/card0-58as-a').relative_to(ROOT)),fault_review=str((P/'evidence/fault-review-58as-a.json').relative_to(ROOT)),chain_command=ready['chain_command'],chain_command_digest_sha256=hashlib.sha256(ready['chain_command'].encode()).hexdigest(),command_hash_encoding='UTF-8, no trailing newline',windows=['K1a','K1b','KD','W2m','WS','WS128x','WS128'],gap_seconds=90,wait_seconds=300,lane='A',card=0,scope='whole-host',configuration=read(P/'runtime-selection.json'),whole_host_hold_required_through_gaps=True,both_lanes_pause_and_drain_required=True,codex_frozen_from='WS',codex_frozen_through='WS128 completion',bracket_rates_tok_s=bracket['rates'],control_drift_fraction=bracket['control_drift_fraction'],minimum_gain=bracket['minimum_gain_vs_best_control'],candidate_beats_all_controls=True,bracket_exact_requests=60,pinned_predecessor=read(P/'submission-policy.json')['supersedes'],submission_scope_tokens=128,strict512_claim=False,fresh_timing_repeat_passed=False,submission_rehearsal_passed=True,chain_native_interface_passed=True,wait_policy_gate_passed=True,python_tests=137,preparation_ram_budget_bytes=2_000_000_000,files_sha256={str(f.relative_to(ROOT)):sha(f) for f in files if f.is_relative_to(P)},orchestration_provenance=[dict(name=f.name,parent_relpath=str(f.relative_to(ROOT)),parent_digest=sha(f)) for f in files if f.is_relative_to(O)],native_identity=[dict(name=n,parent_relpath=str((P/n).relative_to(ROOT)),parent_digest=h) for n,h in read(P/'build-receipt.json')['artifacts'].items()],chain_quality_pending=True,chain_performance_pending=True,no_retry=True,queued=False,device_executed=False,native_recompiled=True,k1_fixture_rebuilt=False,services_started=False,model_payload_reads=False,live_queue_changed=False,submission_performed=False,final_content_write=True)
 for f in (P/'READY-FOR-DEVICE.json',O/'READY-FOR-DEVICE.json'):f.write_text(json.dumps(row,indent=2)+'\n')
 print('Both READY markers written last: READY; chain binary is the wait-policy rebuild')
if __name__=='__main__':main()
