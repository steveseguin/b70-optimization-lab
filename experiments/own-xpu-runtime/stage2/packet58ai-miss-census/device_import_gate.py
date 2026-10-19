"""Closed-environment dependency census and actual sensor-path CPU probe."""
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
P = Path(__file__).resolve().parent
KINDS = ('K1a', 'K1b', 'WSCREEN', 'census')
EXCLUDED = {('launch_env.py', 'check_binary'): 'standalone CPU loader CLI',
            ('supervision.py', 'finalize_r1'): 'unused generic report adapter'}

def imports():
    pending = [P/n for n in ('window.py', 'queue_runner.py', 'suite_driver.py',
               'p56_head_support.py', 'supervision.py', 'screen.py', 'verify_ready.py',
               'host-admission/memory_plan.py')]
    seen = set(); modules = set(); exclusions = []
    while pending:
        path = pending.pop()
        if path in seen: continue
        seen.add(path)
        tree = ast.parse(path.read_text())
        for node in list(ast.walk(tree)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (path.name, node.name) in EXCLUDED:
                exclusions.append(dict(file=path.name, function=node.name, reason=EXCLUDED[path.name,node.name]))
                node.body = []
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                modules.add(name)
                local = P/(name.split('.')[0]+'.py')
                if local.is_file(): pending.append(local)
    return sorted(modules), sorted(str(x.relative_to(P)) for x in seen), exclusions

def probe(kind, blocked=None):
    assert kind in KINDS
    assert Path.cwd() == P.parents[3] and sys.dont_write_bytecode
    assert Path(sys.path[0]).resolve() == P
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = os.fsdecode(args[0])
            if path.startswith('/dev/dri/') or path.endswith('.gguf'):
                raise RuntimeError('CPU import probe forbids device/model access')
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise RuntimeError('CPU import probe forbids process launch')
    sys.addaudithook(audit)
    import window as W
    W.closed_environment()
    if blocked:
        class Missing:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == blocked: raise ModuleNotFoundError("No module named '"+blocked+"'")
        sys.modules.pop(blocked, None)
        sys.meta_path.insert(0, Missing())
    names, files, exclusions = imports()
    for name in names: importlib.import_module(name)
    full = kind in ('WSCREEN', 'census')
    budget = W.M.plan()
    with patch.object(W.SUPPORT, 'process_tree_anon', return_value=dict(root_seen=True, anonymous_bytes=0, processes=[])), patch.object(W.M, 'meminfo', return_value=dict(MemAvailable=200*1024**3, GPUActive=0)):
        sample = W.live_memory_sensor(os.getpid(), full_model=full, budget=budget)
    assert not full or sample['device_occupancy']['passed']
    return dict(passed=True, kind=kind, sensor_path_executed=True, full_model=full,
                cwd=str(Path.cwd()), sys_path_0=sys.path[0], modules=names,
                sources={f:hashlib.sha256((P/f).read_bytes()).hexdigest() for f in files},
                excluded_cpu_only_functions=exclusions, device_executed=False)

def main():
    import launch_env
    rows=[]
    for kind in KINDS:
        command=['/usr/bin/python3','-B',str(P/'window.py'),'--cpu-import-check',kind]
        result=subprocess.run(command,cwd=P.parents[3],env=launch_env.environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
        if result.returncode: raise RuntimeError(result.stderr)
        rows.append(json.loads(result.stdout))
    command += ['--simulate-missing-device-memory']
    old=subprocess.run(command,cwd=P.parents[3],env=launch_env.environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    assert old.returncode and "No module named 'device_memory'" in old.stderr
    report=dict(passed=True,device_executed=False,windows=rows,
                old_tree_regression_rejected=True,old_tree_error=old.stderr.splitlines()[-1],
                environment_keys=sorted(launch_env.environment()),model_payload_reads=False)
    (P/'evidence/device-import-gate.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS all four real-launch import/sensor paths; missing-module regression rejected')
if __name__ == '__main__': main()
