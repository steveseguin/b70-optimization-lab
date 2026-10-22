#!/usr/bin/env python3
"""Compile one CPU-only actual-engine adapter, then run two fresh processes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import build
from storage import cpu_build_admit
P = Path(__file__).resolve().parent
B = P / 'build'
ROOT = P.parents[3]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def run():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32))
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    mode = json.loads((P / 'build-gnu-host-receipt.json').read_text())
    compiled = build.compiled_sources()
    assert mode['compiled_sources_sha256'] == compiled
    objects = sorted((B/'gnu-host/CMakeFiles/programs.dir').rglob('*.o'))
    objects = [p for p in objects if p.name != 'entry-main.cpp.o']
    assert objects and any(p.name == 'p49c_submit.cpp.o' for p in objects)
    obj_hashes = {str(p.relative_to(P)):sha(p) for p in objects}
    source_files = [P/'p49c_engine_fixture.cpp', P/'p49c_engine_gate.py',
                    P.parent/'packet51-round2/fixture_bytes.hpp',
                    P.parent/'packet34-replay-bench/directory.tsv', P/'dispatch-speed6.json']
    source_hashes = compiled | {str(p.relative_to(ROOT)):sha(p) for p in source_files}
    cpu_build_admit(100_000_000)
    out = B / ('engine-fixtures-' + str(time.time_ns()))
    out.mkdir()
    checked = B/'checked'/P.relative_to(ROOT)
    text = (P/'p49c_engine_fixture.cpp').read_text()
    for name in ('main.cpp', 'p49c_submit.hpp', 'route42.hpp'):
        text = text.replace('"'+name+'"', json.dumps(str(checked/name)))
    text = text.replace('"../packet51-round2/fixture_bytes.hpp"', json.dumps(str(source_files[2])))
    source = out/'adapter.cpp'
    source.write_text('#line 1 '+json.dumps(str(P/'p49c_engine_fixture.cpp'))+'\n'+text)
    binary = out/'engine-fixtures'
    command = ['/usr/bin/g++', '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off',
               '-fopenmp', '-DOWN_RT_HOST_ONLY', '-Werror=return-type',
               '-I'+str(P), '-I'+str(P/'../../stage1/packet3-prep/src'),
               '-I'+str(P/'../packet2/kernels'), '-I'+str(P/'../packet2/loader'),
               str(source), *map(str,objects), '-lcrypto', '-o', str(binary)]
    with (out/'compile.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    rows=[]
    for repeat in range(2):
        dest=out/('run'+str(repeat))
        cmd=[str(binary),'--mode','exact','--cpu-test','--output',str(dest)]
        with (out/('run'+str(repeat)+'.log')).open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=3600)
        receipt=json.loads((dest/'receipt.json').read_text())
        assert receipt['passed'] and receipt['cpu_mock'] and not receipt['device_executed']
        assert receipt['safe_to_exit'] and receipt['arithmetic']=='iq3-p49-split32-v1'
        assert receipt['checks'] > 0
        comparisons=[json.loads(line) for line in (dest/'comparisons.jsonl').read_text().splitlines()]
        cases={(r['layer'],r['m'],r['token_row'],r['iteration']) for r in comparisons}
        assert len(cases)==36 and all(r['equal'] for r in comparisons)
        assert {r['layer'] for r in comparisons} == {3,4}
        assert {r['m'] for r in comparisons} == {1,2}
        assert {r['token_row'] for r in comparisons if r['m']==2} == {0,1}
        identity=sha(dest/'comparisons.jsonl')
        assert identity==receipt['exact_output_identity']
        if rows: assert identity==rows[0]['comparison_sha256']
        rows.append(dict(repeat=repeat,command=cmd,receipt=receipt,
                         receipt_sha256=sha(dest/'receipt.json'),comparison_sha256=identity,
                         cases=len(cases),output=str(dest)))
        print('actual-engine fresh process',repeat,'PASS',receipt['checks'],flush=True)
    assert compiled==build.compiled_sources()
    assert obj_hashes == {str(p.relative_to(P)):sha(p) for p in objects}
    result=dict(schema='packet49c.engine-cpu-gate.v1',passed=True,device_executed=False,
                model_weights_read=False,compiled_sources_sha256=compiled,source_hashes=source_hashes,
                baseline_objects=obj_hashes,command=command,binary_sha256=sha(binary),
                rendered_source_sha256=sha(source),fresh_processes=rows,
                scope='Actual Engine execute_site at ordinary GDN4 and QSA3; M1 and serial M2 with carried BF16 recurrence/cache state; original packet49c paths including p49b experts and p30 small tuple form the baseline; default production p54 selectors and banked p53b engine wiring')
    (P/'p49c-engine-gates.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    run()
