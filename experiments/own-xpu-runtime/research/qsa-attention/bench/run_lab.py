#!/usr/bin/env python3
"""Lab runner for the QSA attention study: one rank-1 run on card 27 under the card lock, renderD check, fault check,
state-dump trimming (keeps state.json, which is all `compare` reads)."""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

LAB = Path('/dev/shm/ownrt-lab-attn')
TEMPLATE = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/context-64k/rank1-card27-s24-ctx65536-launch.json')
DRIVER = '/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py'
FAULT = re.compile(r'xe .*(fault|reset|error|timed out)|CAT error|GuC', re.I)

ap = argparse.ArgumentParser()
ap.add_argument('tag')
ap.add_argument('--binary', required=True)
ap.add_argument('--prompt', type=int, default=4096)
ap.add_argument('--steps', type=int, default=48)
ap.add_argument('--env', action='append', default=[])
ap.add_argument('--keep-state', action='store_true')
a = ap.parse_args()

if (LAB / 'HALT').exists():
    sys.exit('HALT marker present: ' + (LAB / 'HALT').read_text())
launch = json.loads(TEMPLATE.read_text())
argv = launch['argv']
idx = [i for i, x in enumerate(argv) if x.endswith('/sc117-engine')]
assert len(idx) == 1, argv
argv[idx[0]] = a.binary
for kv in a.env:
    k, v = kv.split('=', 1)
    launch['environment'][k] = v
assert launch['environment']['FilterBdfPath'] == '0000:27:00.0'
out = LAB / a.tag
lj = LAB / f'launch-{a.tag}.json'
lj.write_text(json.dumps(launch, indent=1))
cmd = ['flock', '/dev/shm/card27.lock', 'nice', '-n', '10', 'taskset', '-c', '8-15,24-31', 'python3', '-B', DRIVER, 'run',
       '--launch', str(lj), '--out', str(out), '--steps', str(a.steps), '--prompt', str(a.prompt), '--batched', '--rows', '32',
       '--cache', str(LAB / 'cache')]
print('cmd', ' '.join(cmd), flush=True)
t_req = time.time()
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
start = None
dri = set()
engine_pid = None
# Poll for the engine process (its --output names our run dir) and record its DRM fds.
import threading
lines = []
def reader():
    for l in proc.stdout:
        lines.append(l)
        print(l, end='', flush=True)
th = threading.Thread(target=reader, daemon=True); th.start()
needle = str(out / 'rank1')
while proc.poll() is None:
    if engine_pid is None:
        for p in os.listdir('/proc'):
            if not p.isdigit():
                continue
            try:
                c = open(f'/proc/{p}/cmdline', 'rb').read().split(b'\0')
            except OSError:
                continue
            if c and c[0].endswith(b'sc117-engine') and needle.encode() in c:
                engine_pid = int(p); start = start or time.time()
                print('engine pid', engine_pid, flush=True)
                break
    if engine_pid is not None:
        try:
            for fd in os.listdir(f'/proc/{engine_pid}/fd'):
                try:
                    t = os.readlink(f'/proc/{engine_pid}/fd/{fd}')
                except OSError:
                    continue
                if t.startswith('/dev/dri/'):
                    if t not in dri:
                        print('dri fd', t, flush=True)
                    dri.add(t)
        except OSError:
            pass
    time.sleep(0.5)
th.join(timeout=5)
rc = proc.returncode
since = int((start or t_req)) - 5
j = subprocess.run(['journalctl', '-k', '--since', f'@{since}', '--no-pager'], capture_output=True, text=True).stdout
faults = [l for l in j.splitlines() if FAULT.search(l)]
res = dict(tag=a.tag, rc=rc, engine_pid=engine_pid, dri=sorted(dri), faults=faults, since=since, env=a.env, binary=a.binary)
summ = out / 'summary.json'
if summ.exists():
    s = json.loads(summ.read_text())
    t = sorted(s['half_ms'])
    res['median_half_ms'] = t[len(t) // 2]
    res['mean_half_ms'] = sum(t) / len(t)
    res['min_half_ms'] = t[0]
    res['tokens_head'] = s['tokens'][:8]
st = out / 'rank1' / 'state-2147483647'
if st.exists() and not a.keep_state:
    for f in st.iterdir():
        if f.name != 'state.json':
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
for f in ('prefill.bin',):
    if (out / f).exists():
        (out / f).unlink()
bad_dri = [d for d in dri if 'renderD131' not in d and 'card4' not in d]
if faults or bad_dri:
    (LAB / 'HALT').write_text(json.dumps(res, indent=1))
    print('HALT', json.dumps(res, indent=1))
(out / 'lab-result.json').write_text(json.dumps(res, indent=1))
print('RESULT', json.dumps({k: v for k, v in res.items() if k != 'faults'}), 'faults', len(faults))
sys.exit(0 if rc == 0 and not faults and not bad_dri else 1)
