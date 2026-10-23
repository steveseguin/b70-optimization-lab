"""Recompute packet194 k3x-diet evidence (rows 0-1, lane B) and all CPU gates immediately before launch."""
import argparse,json,shutil
from chain_adapter import O,P,ROOT,sha
from bracket_gate import evaluate as evaluate_rates, summary as bracket_summary
UNIT='packet195-chain-a'
OUTPUT=P/'build/device-cards01-p195-a'
def command():
 return f"systemd-run --user --unit={UNIT} --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory={ROOT} /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash {O/'device-entry.sh'} chain {OUTPUT} </dev/null"
def evaluate():
 from verify_cpu import verify as cpu
 from bracket_gate import verify as bracket
 from storage import precheck
 policy=json.loads((O/'policy195.json').read_text())
 assert policy['coordinator_idle_lane_exception_authorized'] is True and policy['screen_minimum_gain_percent']==0.5 and policy['chain_minimum_gain_percent']==2.0
 assert policy['chain_lane']=='A' and policy['cards']==[0,1] and policy['host_required_available_bytes']==108797048558 and policy['record_floor_tok_s']==62.345281904743764 and policy['record_hard_floor_tok_s']==62.345282
 proof=bracket();gates=cpu();disk=precheck()
 assert disk['passed'],'device disk reserve unavailable'
 assert not OUTPUT.exists(),'registered output is not fresh'
 return dict(schema='packet195.ready.v1',ready=True,ready_for_device=True,cpu_preparation_ready=True,device_executed=False,queued=False,submitted=False,unit=UNIT,output=str(OUTPUT),chain_output=OUTPUT.name,lane='A',cards=[0,1],chain_command=command(),command=command(),bracket=bracket_summary(proof),cpu=gates,policy_sha256=sha(O/'policy195.json'),storage=disk,scope=dict(output_tokens=128,strict512=False,arithmetic='iq3-p49-split32-v1'),host=dict(required_available_bytes=policy['host_required_available_bytes'],queue_start_extra_bytes=policy['host_queue_start_extra_bytes']),chain_policy='k3x-diet is a screen winner (packet194 s194_decision: slower diet view 63.413 = +1.96 % over every in-load k3x view, every view exact, drift 0.06 %, gate/up saving 10.8-11.8 us per layer); the +2 % chain bar is missed by 0.04 points and the chain is admitted by the coordinator ruling of 2026-10-23 (lanes idle, chain policy allows); fresh exact WS128 must beat 62.345282 (cmvk51wfn001gng01fpbfy89q, ledger 62.345281904743764). Timing windows require existing whole-host admission.')
def verify():
 # Compare in the stored (JSON) form: tuples in the recomputed row serialize as lists.
 actual=json.loads(json.dumps(evaluate()));stored=json.loads((O/'ready.json').read_text())
 assert stored['ready_for_device'] is True
 for key in ('unit','output','lane','cards','chain_command','bracket','cpu','policy_sha256','scope','host'):assert stored[key]==actual[key],'readiness identity changed: '+key
 return actual
if __name__=='__main__':print(json.dumps(verify(),indent=2))
