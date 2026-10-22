"""Fixed banked bundle8 plus one exact class-layout dimension."""
from common import HERE,ROOT,P56,read,require,sha,module
VALUES=('production',)   # packet184: bundle 8 (snapshot_host production) is the only registered lineage
def sealed_identity(args):
 from cpu_seal import verify
 row=verify();line=args.lineage.resolve()
 require(line.parent==HERE/'lineage' and line.name in VALUES,'registered class bank required')
 require(args.profile=='tp2' and args.placement=='1' and args.timing=='token','fixed two-card token timing required')
 binary=HERE/'build/device/own-rt-iq3';dispatch=line/'dispatch-speed6.json';seal=line/'screen-seal.json'
 for value,path in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):require(value is None or value.resolve()==path,'sealed input differs')
 gate=module('p150_memory',P56/'memory_gate.py');configuration=gate.configuration(read(line/'memory-plan.json'),4096,1,0)
 placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],context=4096,memory_admitted=True,supported=True,reason='packet136 budget plus inherited probe scratch and 64 KiB immutable descriptor reserve on rank0',configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(line),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(line/'selection.json'),memory_plan_sha256=sha(line/'memory-plan.json'))
