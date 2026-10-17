#!/usr/bin/env python3
"""All sealed CPU suites and plans. No runtime audit, payload read or GPU tools."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
OUT = REPO / 'data/2026-10-17-flash-next-a367-glue01-build'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) == set(range(4,16)) | set(range(20,32))
    OUT.mkdir(exist_ok=True)
    suites = [
        ('glue01', HERE, 'test_*.py', '/usr/bin/python3'),
        ('census', HERE.parent/'a367-census', 'test_*.py', '/usr/bin/python3'),
        ('replay', HERE.parent/'a367-replay', 'test_replay.py', '/usr/bin/python3'),
        ('calibration', HERE.parent/'a367-calibrate', 'test_calibrate.py', '/usr/bin/python3'),
        ('driver', HERE.parent/'driver', 'test_driver.py', '/home/steve/.venvs/vllm-xpu/bin/python3'),
        ('payload', REPO/'scripts', 'test_verify_flash_next_a367_launch_payload.py', '/usr/bin/python3'),
        ('tree', REPO/'scripts', 'test_verify_qwen38_flash_next_fp8_tree.py', '/usr/bin/python3'),
        ('feasibility', HERE.parent/'a367-census/feasibility', 'test_cpu.py', '/usr/bin/python3'),
    ]
    result = {'schema':'a367-glue01-cpu-build.v1','native_executed':False,'model_weights_read':False,
        'owner_window_created':False,'nice':19,'affinity':sorted(os.sched_getaffinity(0)),
        'suites':[],'seals':[],'plans':[]}
    for name, directory, pattern, python in suites:
        command = [python,'-B','-m','unittest','discover','-s',str(directory),'-p',pattern,'-v']
        run = subprocess.run(command,cwd=REPO,capture_output=True,text=True,env={**os.environ,'OMP_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1'})
        output = run.stdout + run.stderr
        log = OUT/(name+'-tests.log'); log.write_text(output)
        match = re.search(r'Ran (\d+) tests?',output)
        count = int(match[1]) if match else 0
        passed = run.returncode == 0 and count > 0 and re.search(r'^OK\s*$',output,re.M) is not None
        result['suites'].append({'suite':name,'command':command,'tests':count,'passed':passed,
            'returncode':run.returncode,'log':log.name,'log_sha256':sha(log)})
        print(f'{name}: {count} tests, passed={passed}',flush=True)
    for seal in (HERE/'seal.json',HERE.parent/'a367-census/seal.json',HERE.parent/'a367-replay/seal.json',
                 HERE.parent/'a367-calibrate/seal.json',HERE.parent/'driver/driver-seal.json'):
        files = json.loads(seal.read_text())['files']
        root = seal.parent if seal.name == 'driver-seal.json' else REPO
        mismatches = [p for p,d in files.items() if not(root/p).is_file() or sha(root/p)!=d]
        result['seals'].append({'path':str(seal.relative_to(REPO)),'sha256':sha(seal),'files':len(files),'mismatches':mismatches})
    for arm in ('control','candidate'):
        command = ['/usr/bin/python3','-B',str(HERE/'a367_glue01.py'),'--plan','--arm',arm,
                   '--output',f'/mnt/raid-models/bench-results/a367g-20261017T000000Z-{arm}']
        run = subprocess.run(command,capture_output=True,text=True,check=True)
        plan = json.loads(run.stdout); assert plan['native_executed'] is False
        path = OUT/(arm+'-plan.json'); path.write_text(run.stdout)
        result['plans'].append({'arm':arm,'path':path.name,'sha256':sha(path)})
    for path in HERE.glob('*.sh'):
        subprocess.run(['bash','-n',str(path)],check=True)
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(),filename=str(path))
    import a367_glue01 as c
    import operator_gate
    result['export_verification'] = c.verify_export()
    operator = operator_gate.cpu_gate()
    c.w.write(OUT/'operator-cpu.json', operator)
    result['operator_cpu_cases'] = operator['case_count']
    result['operator_device_qualified'] = False
    result['tests'] = sum(row['tests'] for row in result['suites'])
    result['seal_mismatches'] = sum(len(row['mismatches']) for row in result['seals'])
    result['preregistration_sha256'] = sha(HERE/'preregistration.json')
    result['seal_sha256'] = sha(HERE/'seal.json')
    result['approval_sentence'] = c.glue_approval_text()
    result['passed'] = all(row['passed'] for row in result['suites']) and result['seal_mismatches']==0
    c.w.write(OUT/'receipt.json',result)
    print(json.dumps({'tests':result['tests'],'operator_cpu_cases':operator['case_count'],
                      'passed':result['passed'],'seal_mismatches':result['seal_mismatches']}))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    sys.exit(main())
