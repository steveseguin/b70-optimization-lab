"""After smoke shipment, finish CPU chain preparation and proposals; never execute."""
import json,subprocess,sys
from source_decision import O,ROOT,P,save

def main():
 for cmd in ([sys.executable,'-B',str(O/'source_decision.py')],):subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,check=True)
 from composite_jobs import current,generate
 _,config=current()
 flags=[x for k,v in config['candidate'].items() for x in ('--'+k,v)]
 for label,cmd in [('policy',[sys.executable,'-B',str(O/'policy_seal.py')]),('reseal',[sys.executable,'-B',str(O/'chain_adapter.py'),'fast_reseal.py',*flags]),('inputs',[sys.executable,'-B',str(O/'chain_adapter.py'),'check_inputs.py']),('chain-plan',[sys.executable,'-B',str(O/'chain_entry.py'),'queue','--plan','--output-root',str(P/'build/device-cards01-a')])]:
  with (O/(label+'.log')).open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=240)
  assert r.returncode==0,label
 generate()
 from verify_ready import evaluate
 save(O/'ready.json',evaluate())
 print('CPU preparation complete; readiness:',json.loads((O/'ready.json').read_text())['ready'])
if __name__=='__main__':main()
