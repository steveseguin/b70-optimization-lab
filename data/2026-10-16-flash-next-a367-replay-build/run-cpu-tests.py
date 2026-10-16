"""Lean CPU-only receipt runner. Never invokes GPU probes or execute mode."""
from pathlib import Path
import datetime, hashlib, json, os, re, subprocess, sys
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PREP = ROOT / 'experiments/own-xpu-runtime/stage1/packet4-prep'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19
assert os.sched_getaffinity(0) == set(range(4,16)) | set(range(20,32))
suites = [
    ('replay', '/usr/bin/python3', PREP/'a367-replay', 'test_replay.py'),
    ('calibration', '/usr/bin/python3', PREP/'a367-calibrate', 'test_calibrate.py'),
    ('driver', '/home/steve/.venvs/vllm-xpu/bin/python3', PREP/'driver', 'test_driver.py'),
    ('payload', '/usr/bin/python3', ROOT/'scripts', 'test_verify_flash_next_a367_launch_payload.py'),
    ('frozen-tree', '/usr/bin/python3', ROOT/'scripts', 'test_verify_qwen38_flash_next_fp8_tree.py'),
]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
rows=[]
for name, python, folder, pattern in suites:
    command=[python, '-B', '-m', 'unittest', 'discover', '-s', str(folder), '-p', pattern, '-v']
    log=OUT/(name+'.log')
    with log.open('w') as stream:
        result=subprocess.run(command, cwd=ROOT, env=dict(os.environ, OMP_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'), stdout=stream, stderr=subprocess.STDOUT)
    text=log.read_text()
    count=int(re.search(r'Ran (\d+) tests?', text)[1])
    passed=result.returncode == 0 and bool(re.search(r'^OK$', text, re.M))
    rows.append(dict(suite=name, command=command, tests=count, returncode=result.returncode,
                     passed=passed, failures=len(re.findall(r'^FAIL: ', text, re.M)),
                     errors=len(re.findall(r'^ERROR: ', text, re.M)), skips=len(re.findall(r' \.\.\. skipped ', text)),
                     log=log.name, log_sha256=sha(log)))
    print(name, count, 'PASS' if passed else 'FAIL', flush=True)
sys.path.insert(0, str(PREP/'a367-replay'))
import a367_replay as replay
replay.verify_seals()
seals=[]
for path in [PREP/'a367-replay/seal.json', PREP/'a367-calibrate/seal.json', PREP/'driver/driver-seal.json']:
    data=json.loads(path.read_text())
    files=data['files']
    base=path.parent if path.name == 'driver-seal.json' else ROOT
    bad=[key for key, digest in files.items() if sha(base/key) != digest]
    seals.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), files=len(files), mismatches=bad))
plan=OUT/'plan.json'
with plan.open('w') as stream:
    subprocess.run(['/usr/bin/python3','-B',str(PREP/'a367-replay/a367_replay.py'),'--plan',
                    '--output','/mnt/raid-models/bench-results/a367r-20261016T000000Z'], check=True,
                   stdout=stream, cwd=ROOT)
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), suites=rows,
             tests=sum(row['tests'] for row in rows), passed=all(row['passed'] for row in rows) and not any(s['mismatches'] for s in seals),
             seals=seals, seal_mismatches=sum(len(s['mismatches']) for s in seals),
             preregistration_sha256=sha(PREP/'a367-replay/preregistration.json'),
             nice=19, affinity=sorted(os.sched_getaffinity(0)), native_executed=False,
             plan_sha256=sha(plan))
(OUT/'cpu-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
assert receipt['passed'], receipt
print('TOTAL', receipt['tests'], 'seal mismatches', receipt['seal_mismatches'])
