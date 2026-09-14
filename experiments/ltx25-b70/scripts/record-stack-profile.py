#!/usr/bin/env python3
"""One read-only py-spy attachment and one unchanged clip; no server control."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
spec = importlib.util.spec_from_file_location('stability', LANE / 'scripts/run-stability.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
binding = module.identity_binding(ROOT)
out = ROOT / 'stack-profile-01'
out.mkdir(exist_ok=False)
(out / 'identity.json').write_text(json.dumps(binding, indent=2) + '\n')
command = ['sudo', '-S', '-p', '', '/home/steve/.local/bin/py-spy', 'record',
           '--pid', str(binding['pid']), '--duration', '15', '--rate', '100',
           '--threads', '--idle', '--nonblocking', '--full-filenames',
           '--format', 'speedscope', '--output', str(out / 'stacks.json')]
(out / 'profiler-command.json').write_text(json.dumps(command, indent=2) + '\n')
with Path('/home/steve/SUDOPASSWORD.txt').open('rb') as credential, (out / 'profiler.log').open('xb') as log:
    profiler = subprocess.Popen(command, stdin=credential, stdout=log, stderr=subprocess.STDOUT)
    (out / 'profiler-pid.json').write_text(json.dumps({'pid': profiler.pid}) + '\n')
    deadline = time.monotonic() + 12
    try:
        while True:
            text = (out / 'profiler.log').read_text(errors='replace')
            if 'Sampling process' in text and profiler.poll() is None:
                break
            if profiler.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('profiler did not confirm attachment; no request submitted')
            time.sleep(.1)
        module.identity_binding(ROOT, binding)
        request = [sys.executable, str(LANE / 'scripts/profile-clip.py'), 'stack-profile-01',
                   '--graph', str(LANE / 'data/speed-resident-split-api.json'),
                   '--server-run', str(ROOT / 'speed-server'), '--timeout', '600']
        (out / 'request-command.json').write_text(json.dumps(request, indent=2) + '\n')
        with (out / 'request.log').open('x') as transcript:
            result = subprocess.run(request, stdout=transcript, stderr=subprocess.STDOUT, timeout=650)
        assert result.returncode == 0, 'request failed; no retry'
    finally:
        # The profiler has its own fixed 15-second lifetime; never signal the server.
        code = profiler.wait(timeout=25)
        (out / 'profiler-result.json').write_text(json.dumps({'exit_code': code}) + '\n')
    assert code == 0 and (out / 'stacks.json').exists(), 'profile failed'
module.identity_binding(ROOT, binding)
print(json.dumps({'status': 'captured; exact output comparison pending', 'path': str(out)}))
