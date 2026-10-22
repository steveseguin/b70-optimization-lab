"""Recompute packet186 V3 evidence (rows 0-3) and all CPU gates immediately before launch."""
import argparse,json,shutil
from chain_adapter import O,P,ROOT,sha
from bracket_gate import evaluate as evaluate_rates, summary as bracket_summary
UNIT='packet187-chain-a'
OUTPUT=P/'build/device-cards01-p187-a'
def command():
 return f"systemd-run --user --unit={UNIT} --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory={ROOT} /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash {O/'device-entry.sh'} chain {OUTPUT} </dev/null"
def evaluate():
 from verify_cpu import verify as cpu
 from bracket_gate import verify as bracket
 from storage import precheck
 policy=json.loads((O/'policy187.json').read_text())
 assert policy['coordinator_idle_lane_exception_authorized'] is False and policy['screen_minimum_gain_percent']==2.0
 assert policy['chain_lane']=='A' and policy['cards']==[0,1]
 proof=bracket();gates=cpu();disk=precheck()
 assert disk['passed'],'device disk reserve unavailable'
 assert not OUTPUT.exists(),'registered output is not fresh'
 return dict(schema='packet187.ready.v1',ready=True,ready_for_device=True,cpu_preparation_ready=True,device_executed=False,queued=False,submitted=False,unit=UNIT,output=str(OUTPUT),chain_output=OUTPUT.name,lane='A',cards=[0,1],chain_command=command(),command=command(),bracket=bracket_summary(proof),cpu=gates,policy_sha256=sha(O/'policy187.json'),storage=disk,scope=dict(output_tokens=128,strict512=False,arithmetic='iq3-p49-split32-v1'),host=dict(required_available_bytes=policy['host_required_available_bytes'],queue_start_extra_bytes=policy['host_queue_start_extra_bytes']),chain_policy='V3 meets the +2% record-chain rule (packet186 s186_decision); fresh exact WS128 must beat 58.798109. Timing windows require existing whole-host admission.')
def verify():
 # Compare in the stored (JSON) form: tuples in the recomputed row serialize as lists.
 actual=json.loads(json.dumps(evaluate()));stored=json.loads((O/'ready.json').read_text())
 assert stored['ready_for_device'] is True
 for key in ('unit','output','lane','cards','chain_command','bracket','cpu','policy_sha256','scope','host'):assert stored[key]==actual[key],'readiness identity changed: '+key
 return actual
if __name__=='__main__':print(json.dumps(verify(),indent=2))
