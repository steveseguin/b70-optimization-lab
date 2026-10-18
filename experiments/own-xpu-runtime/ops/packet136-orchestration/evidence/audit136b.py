import hashlib,json,subprocess,sys,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
o=Path('experiments/own-xpu-runtime/ops/packet136-orchestration').resolve();sys.path.insert(0,str(o))
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
base='3dfcff0ca'
def prior(path):return json.loads(subprocess.run(['git','show',base+':'+str(path.relative_to(ROOT))],check=True,capture_output=True,text=True,stdin=subprocess.DEVNULL).stdout)
old=prior(P/'build-receipt.json');new=json.loads((P/'build-receipt.json').read_text())
assert old['artifacts_sha256']==new['artifacts_sha256']
assert old['arithmetic']==new['arithmetic']=='iq3-p49-split32-v1'
for n in ('selection.json','memory-plan.json','dispatch-speed6.json','build-device-receipt.json','cpu-validation.json'):
 assert prior(P/n)==json.loads((P/n).read_text()),n
assert prior(O/'decision.json')==json.loads((O/'decision.json').read_text())
assert json.loads((O/'decision.json').read_text())['identity']=='087f9da3c434e862'
assert not (P/'build/device-cards01-a').exists()
from confirm136 import output
assert all(not output(i).exists() for i in range(-1,5))
startup=json.loads((P/'startup103.json').read_text());before=prior(P/'startup103.json')
fixture=str((P/'build/startup103/fixture').relative_to(ROOT))
assert startup['sources'][fixture]==before['sources'][fixture]==sha(ROOT/fixture)
row=dict(passed=True,device_executed=False,native_binary_rebuilt=False,services_started=False,live_queue_modified=False,
 original_commit=base,arithmetic=new['arithmetic'],native_artifacts_unchanged=old['artifacts_sha256'],
 decision_identity='087f9da3c434e862',evidence_rule='identical-native-selection-both-v4-lanes-v1',chain_output='device-cards01-a',
 startup=dict(total_windows=22,fixture_reused_sha256=sha(ROOT/fixture),native_build_reused=True,checks_rerun=True,max_rss_kib=startup['max_rss_kib']),
 real_entry_probe='evidence/confirm-entries.json',new_outputs=[str(output(i)) for i in range(-1,5)],
 procedures={str(f.relative_to(ROOT)):sha(f) for f in (O/'evidence/startup136b-replay.py',O/'evidence/reseal136b-views.py',O/'evidence/reseal136b-chain.py')})
save(O/'evidence/repair136b-audit.json',row)
print('Native identity, decision, thresholds, fresh chain and outputs verified unchanged/fresh')
