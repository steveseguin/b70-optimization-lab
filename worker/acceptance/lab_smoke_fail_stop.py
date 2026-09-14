#!/usr/bin/env python3
"""Independent fake-command acceptance, following tools/test_container_packet_smoke.py's approach."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path.cwd()
SCRIPT = ROOT / 'tools/container-packet/smoke-test.sh'
assert SCRIPT.is_file(), 'Run acceptance from the repository workspace'

with tempfile.TemporaryDirectory(prefix='packet-fail-stop-') as temporary:
    root = Path(temporary)
    commands = root / 'commands'
    commands.mkdir()
    for name, source in {
        'docker': '''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['DOCKER_RECEIPT'],'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')
if 'ps' in sys.argv: print('running')
''',
        'curl': '''#!/usr/bin/env python3
import os,sys
from pathlib import Path
if any(arg.endswith('/health') for arg in sys.argv): sys.exit(0)
root=Path(os.environ['CASE_DIR'])
counter=root/'requests.txt'
n=int(counter.read_text())+1 if counter.exists() else 1
counter.write_text(str(n))
if os.environ['FIRST_FAIL']=='1' and n==1:
    print('{"error":"first request failed"}')
    sys.exit(22)
print('{"choices":[{"text":"A tensor is a multidimensional array."}],"usage":{"completion_tokens":8}}')
''',
    }.items():
        executable = commands / name
        executable.write_text(source)
        executable.chmod(0o755)
    # A working successful pair is a control against simply disabling the smoke test.
    for failure in (False, True):
        case = root / ('failure' if failure else 'success')
        case.mkdir()
        out = case / 'out'
        env = {'PATH': f'{commands}:/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
               'CASE_DIR': str(case), 'DOCKER_RECEIPT': str(case / 'docker.jsonl'),
               'FIRST_FAIL': '1' if failure else '0', 'PACKAGE_DIR': 'packages/qwen35-4b-w4a16-b70',
               'SERVED_NAME': 'acceptance-model', 'MODEL_DIR': str(case), 'OUT_DIR': str(out),
               'VLLM_CACHE_DIR': str(case / 'cache'), 'KEEP_UP': '0', 'PROFILE': 'one-gpu'}
        result = subprocess.run(['bash', str(SCRIPT)], cwd=ROOT, env=env, text=True,
                                capture_output=True, timeout=15)
        attempts = int((case / 'requests.txt').read_text())
        docker = [json.loads(line) for line in (case / 'docker.jsonl').read_text().splitlines()]
        assert sum('up' in argv for argv in docker) == 1, 'Smoke must not restart the server'
        if failure:
            assert attempts == 1, f'First failed request was followed by another generation ({attempts} attempts)'
            assert result.returncode != 0, 'First transport failure must fail the smoke test'
            assert (out / 'answer-1.json').exists(), 'Available first-response evidence must be retained'
            assert 'first request failed' in (out / 'answer-1.json').read_text(), 'First response body was lost'
            assert not (out / 'result.json').exists(), 'Failure must not create a passing result receipt'
            assert 'PASS ' not in result.stdout, 'Failure must not be reported as a pass'
        else:
            assert result.returncode == 0, result.stdout + result.stderr
            assert attempts == 2, 'Successful smoke still requires two generations'
            assert json.loads((out / 'result.json').read_text())['repeat_exact'] is True
print('PASS: successful pair preserved; first transport failure stops further generation and retains evidence')
