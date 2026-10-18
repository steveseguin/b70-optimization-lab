import sys,json,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
o=Path('experiments/own-xpu-runtime/ops/packet136-orchestration').resolve();sys.path.insert(0,str(o))
from source_decision import O,P,save,sha
from policy_seal import NAMES,verify
save(O/'policy-seal.json',dict(passed=True,device_executed=False,sources={str((O/n).relative_to(O.parents[3])):sha(O/n) for n in NAMES}));verify()
from chain_adapter import install
install()
from chain_seal import checked,verify
old=P/'build-receipt.json';archive=P/'evidence'/('prior-chain-seal-'+sha(old)+'.json')
if not archive.exists():archive.write_bytes(old.read_bytes())
save(old,checked())
from packet56_submission import pin_resealed_packet56
pin_resealed_packet56();verify()
print('Minimal chain source seal and submission binding refreshed; native artifacts unchanged')
