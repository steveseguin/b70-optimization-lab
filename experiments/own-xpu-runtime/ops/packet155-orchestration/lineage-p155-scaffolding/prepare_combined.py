"""CPU-only packet124r selection and planning; never reseal frozen views."""
import json
import os
import subprocess
import sys
from source_decision import O,ROOT,P,save,sha


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    from composite_jobs import current,validate,view,generate
    _,config=current();validate(config)
    from chain_adapter import install
    install()
    from storage import B
    from stopped_archive import require_fresh_chain
    require_fresh_chain(B)
    lineage=view(config['candidate'])
    for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json','screen-seal.json'):
        (P/leaf).write_bytes((lineage/leaf).read_bytes())
    from bundle_selection import KEYS,name,PLACEMENTS
    rank,split,boundary=PLACEMENTS['1']
    save(P/'bundle-selection.json',dict(config['candidate'],name=name(*(config['candidate'][k] for k in KEYS)),
        placement='1',draft='draft-hc',miss={'copy':'batch','banks':'banks-batch'}[config['candidate']['rollback_state']],draft_rank=rank,target_split=split,layer_boundary=boundary,
        selection_sha256=sha(P/'selection.json'),screen_seal_sha256=sha(lineage/'screen-seal.json')))
    from chain_seal import checked,verify
    save(P/'build-receipt.json',checked())
    from packet56_submission import pin_resealed_packet56
    pin_resealed_packet56();verify()
    for label,args in [('inputs',['chain_adapter.py','check_inputs.py']),
                       ('chain-inputs',['chain_adapter.py','check_inputs.py'])]:
        with (O/('p124-'+label+'.log')).open('w') as out:
            r=subprocess.run([sys.executable,'-B',str(O/args[0]),*args[1:]],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=240)
        assert r.returncode==0,label
    generate()
    from verify_ready import evaluate
    result=evaluate();save(O/'ready.json',result);save(O/'p124-ready.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
