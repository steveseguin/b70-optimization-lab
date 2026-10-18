"""Real shared worker imports and lane policies in its closed runtime environment."""
import json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha

def main():
    limits()
    sys.path.insert(0,str(P.parent/'screen/v4-lanes'))
    from common import W,DISPATCH
    wrapper=P.parent/'screen/v4-lanes'
    sys.path.insert(0,str(P.parents[1]/'ops/lane-queue'))
    import lanequeue
    environment=W.closed_environment(lanequeue.closed_env(lanequeue.library_path()))
    code="import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope('A','screen')=='lane-A';assert admission_scope('B','screen')=='lane-B';assert admission_scope('A','WS128')=='whole-host';print('closed worker imports and A/B screen policies PASS')"
    command=[sys.executable,'-B','-c',code,str(wrapper)]
    result=subprocess.run(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60)
    (P/'evidence/startup-imports.log').write_text(result.stdout+result.stderr)
    dispatch=json.loads((P/'dispatch-speed6.json').read_text());DISPATCH.validate(dispatch)
    merged,_=DISPATCH.merge([dispatch,dispatch]);assert merged==dispatch
    from bundle_selection import VIEWS,selection
    shape=json.loads((P/'evidence/full-shape.json').read_text())
    for name in VIEWS:
        selected=selection(name)
        rows=[r for r in shape['runs'] if r['view']==name]
        assert len(rows)==2 and all(r['passed'] and r['selection_key_consumers_verified'] for r in rows)
        assert selected['choices']['experts']==('exp-halfcache' if name=='production' else name)
    files=[P/'startup_import_gate.py',P/'bundle_selection.py',P/'lineage-inputs/control-selection.json',P/'dispatch-speed6.json',P/'evidence/full-shape.json',wrapper/'tp2_worker.py',wrapper/'common.py',wrapper/'lane_admission.py',Path(DISPATCH.__file__)]
    save(P/'evidence/startup-imports.json',dict(passed=True,device_executed=False,command=command,
       sources={str(f.relative_to(ROOT)):sha(f) for f in files},selections=list(VIEWS),lanes=['A','B'],window='screen',
       model_screen_initial_exact_gate_tokens=64,dispatch_merge_unchanged=True,
       record_chain_ready=False,record_chain_scope='No packet102 record-chain proposal. Every chain-window host-reference path still requires qualification; inherited packet97 KD halfcache refusal is not waived.'))
    print(result.stdout.strip())
if __name__=='__main__':main()
