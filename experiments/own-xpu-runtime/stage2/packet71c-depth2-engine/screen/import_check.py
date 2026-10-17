"""Import the real worker closure without entering its device run function."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]

def launch(lane):
    # Same literal file and three-variable environment as lanequeue.py.
    values = []
    for line in Path('/tmp/claude-1000/-home-steve/fn-run/p49.env').read_text().splitlines():
        line = line.strip()
        if line.startswith(('P49_LDP=', 'export P49_LDP=')):
            words = shlex.split(line, comments=True)
            if words[0] == 'export': words.pop(0)
            if len(words) != 1: raise ValueError('invalid literal library assignment')
            values.append(words[0].split('=', 1)[1])
    if len(values) != 1 or not values[0] or any(c in values[0] for c in '$`\n\x00'):
        raise ValueError('missing literal library assignment')
    from devices import masked_environment
    env = masked_environment(lane, dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH=values[0]))
    result = subprocess.run(['/usr/bin/python3', '-B', str(Path(__file__).resolve()), '--check', '--lane', lane],
                            env=env, cwd=ROOT, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=30)
    if result.returncode: raise RuntimeError('worker import check failed:\n' + result.stderr)
    return json.loads(result.stdout)

def check(lane):
    opened = set()
    def audit(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.connect'):
            raise RuntimeError('import attempted process/network activity')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).absolute()
            if str(path).startswith(('/dev/dri/', '/sys/class/drm/')):
                raise RuntimeError('import attempted device access')
            if path.is_relative_to(ROOT): opened.add(path)
            if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                raise RuntimeError('import attempted a filesystem write')
    sys.addaudithook(audit)
    import tp2_worker
    from placement import verify_identity, admission_gate
    _, memory = admission_gate(HERE.parent)
    sys.modules['memory_gate'] = memory
    from devices import masked_environment
    masked_environment(lane, inherited=True)
    modules = tp2_worker.runtime_modules()
    from common import D
    D.oracle_inputs()
    modules[1].checker_module(HERE.parent.parent/'packet49-integrate/oracle/suite_check.py')
    memory.configuration(json.loads((HERE.parent/'memory-plan.json').read_text()),4096,1,0)
    # Include source paths even when Python read an existing bytecode cache,
    # including modules loaded through spec loaders outside sys.modules.
    import types
    pending=list(sys.modules.values()); seen=set()
    while pending:
        module=pending.pop()
        if not isinstance(module,types.ModuleType) or id(module) in seen: continue
        seen.add(id(module))
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_relative_to(ROOT) and path.suffix=='.py': opened.add(path)
        pending.extend(v for v in vars(module).values() if isinstance(v,types.ModuleType))
    assert [m.__name__ for m in modules] == ['pipeline', 'suite', 'storage']
    assert all(Path(m.__file__).resolve().parent == HERE.parent for m in modules)
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(opened) if p.is_file() and p.suffix != '.pyc'}
    return dict(passed=True, device_executed=False, model_executed=False,
                worker=str(HERE/'tp2_worker.py'), runtime_modules=[m.__name__ for m in modules],
                closed_environment=True, files=files)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); ap.add_argument('--lane', choices=('A','B'), required=True)
    a = ap.parse_args(); print(json.dumps(check(a.lane) if a.check else launch(a.lane), indent=2))
