#!/usr/bin/env python3
"""Run two fresh CPU processes per compiler and validate their complete outputs."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import os
from build import HERE,ROOT,sha,limits
from summarize import exact,require

def run():
    limits();out=HERE/'evidence'/('cpu-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='ownrt.packet48.cpu-gates.v1',passed=False,device_executed=False,
                builds={},files={},repeats={},source_hashes={})
    for kind in ('gnu','intel'):
        bp=HERE/f'build-{kind}.json';b=json.loads(bp.read_text())
        require(b['passed'] and b['device_executed'] is False,'CPU build missing')
        for p,h in b['sources'].items():require(sha(ROOT/p)==h,'source changed after CPU build: '+p)
        for p,h in b['artifacts'].items():require(sha(HERE/p)==h,'binary changed after CPU build: '+p)
        result['builds'][kind]=sha(bp);result['source_hashes'].update(b['sources'])
        result['repeats'][kind]=[];unit_outputs=[]
        for repeat in (1,2):
            stem=out/f'{kind}-{repeat}';unit=out/f'{kind}-{repeat}-unit.stdout';err=out/f'{kind}-{repeat}-unit.stderr'
            with unit.open('w') as stdout,err.open('w') as stderr:
                subprocess.run([str(HERE/'build'/kind/'gemv_cpu_test')],check=True,stdout=stdout,stderr=stderr)
            unit_outputs.append(unit.read_text());lines=[json.loads(x) for x in unit.read_text().splitlines()]
            require(lines[-1].get('passed') is True and lines[-1].get('checks',0)>400000,'unit coverage')
            with (out/f'{kind}-{repeat}-bench.stdout').open('w') as stdout,(out/f'{kind}-{repeat}-bench.stderr').open('w') as stderr:
                subprocess.run([str(HERE/'build'/kind/'bench'),'--cpu-test','--mode','exact','--output',str(stem)],check=True,stdout=stdout,stderr=stderr)
            r=exact(stem,cpu=True);require(r['mode']=='exact','CPU exact mode')
            result['repeats'][kind].append(dict(path=str(stem.relative_to(HERE)),receipt=r,unit_checks=lines[-1]['checks']))
        require(unit_outputs[0]==unit_outputs[1],'fresh unit output drift')
        require(result['repeats'][kind][0]['receipt']['exact_output_identity']==result['repeats'][kind][1]['receipt']['exact_output_identity'],'fresh CPU output drift')
    result['files']={str(p.relative_to(HERE)):sha(p) for p in out.rglob('*') if p.is_file()}
    result['source_hashes'].update({str((HERE/n).relative_to(ROOT)):sha(HERE/n) for n in ('cpu_gates.py','summarize.py')})
    result['passed']=True
    (HERE/'cpu-gates.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,device_executed=False,repeats=4,byte_cases=504,
                         unit_checks=[v[0]['unit_checks'] for v in result['repeats'].values()])))

if __name__=='__main__':run()
