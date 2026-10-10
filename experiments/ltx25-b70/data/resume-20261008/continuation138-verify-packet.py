#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read-only recursive verification of sealed138 and its authored components."""
import importlib.util
import json
import os
import sys
from pathlib import Path

assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'Run with nice -n 19'
assert os.environ.get('OMP_NUM_THREADS') == '2', 'Run with OMP_NUM_THREADS=2'
sys.dont_write_bytecode = True


def audit(event, args):
    if event == 'import' and args[0].split('.')[0] in ('torch', 'comfy', 'nodes'):
        raise RuntimeError('Packet verifier refuses GPU/runtime imports')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.realpath(os.fsdecode(args[0]))
        if path == '/dev/dri' or path.startswith('/dev/dri/'):
            raise RuntimeError('Packet verifier refuses device opens')
    if event == 'subprocess.Popen':
        executable, argv, _, _ = args
        allowed = (executable == 'git' and isinstance(argv, (list, tuple))
                   and len(argv) >= 6 and argv[:3] == ['git', '--no-replace-objects', '-C']
                   and argv[4] in ('rev-parse', 'ls-tree', 'show'))
        if not allowed:
            raise RuntimeError('Packet verifier allows only inherited read-only Git source checks')
    if event in ('socket.connect', 'socket.bind', 'os.kill', 'os.killpg'):
        raise RuntimeError('Packet verifier refuses network, signals and child programs')


sys.addaudithook(audit)
LANE = Path(__file__).resolve().parents[2]
AUTHOR = LANE / 'recovery/20261010-continuation138-stream'
OUT = Path(__file__).resolve().parent / 'continuation138-tests'
spec = importlib.util.spec_from_file_location('verify138', AUTHOR/'runtime_packet.py')
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
seal = json.loads((OUT/'seal.json').read_text())
manifest = rp.verify_packet(rp.PACKET, seal['manifest_sha256'])
plan = json.loads((rp.PACKET/'resolution/stream-plan.json').read_text())
assert not list(rp.PACKET.rglob('__pycache__')) + list(rp.PACKET.rglob('*.pyc'))
for name in rp.COMPONENTS:
    assert rp.sha(AUTHOR/name) == rp.sha(rp.PACKET/'resolution/components'/name), name
result = dict(status='source-closure-verified', recursive_parent_verification=True,
    manifest_sha256=seal['manifest_sha256'], plan_sha256=plan['plan_sha256'],
    bound_files=len(manifest['files']), physical_files=sum(p.is_file() for p in rp.PACKET.rglob('*')),
    pycache_count=0, pyc_count=0, author_components_match=True, model_requests=0)
with (OUT/'recursive-verification.json').open('x') as handle:
    handle.write(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
