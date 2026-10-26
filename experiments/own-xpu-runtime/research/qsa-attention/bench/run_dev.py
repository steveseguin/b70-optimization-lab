#!/usr/bin/env python3
"""Run one device command (the microbenchmark) on card 27 only, under the card lock, with DRM fd and fault checks."""
import json, os, re, subprocess, sys, threading, time
from pathlib import Path
LAB = Path('/dev/shm/ownrt-lab-attn')
FAULT = re.compile(r'xe .*(fault|reset|error|timed out)|CAT error|GuC', re.I)
if (LAB / 'HALT').exists():
    sys.exit('HALT marker present')
env = dict(os.environ)
env.update({'NEOReadDebugKeys': '1', 'FilterBdfPath': '0000:27:00.0', 'ZE_ENABLE_PCI_ID_DEVICE_ORDER': '1', 'ZE_AFFINITY_MASK': '0',
            'ONEAPI_DEVICE_SELECTOR': 'level_zero:0', 'SYCL_CACHE_DIR': str(LAB / 'cache/bench-sycl'), 'NEO_CACHE_DIR': str(LAB / 'cache/bench-neo'),
            'SYCL_CACHE_PERSISTENT': '1'})
env['LD_LIBRARY_PATH'] = '/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
cmd = ['flock', '/dev/shm/card27.lock', 'nice', '-n', '10', 'taskset', '-c', '8-15,24-31'] + sys.argv[1:]
t0 = time.time()
proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
dri = set(); target = sys.argv[1]
def reader():
    for l in proc.stdout:
        print(l, end='', flush=True)
th = threading.Thread(target=reader, daemon=True); th.start()
pid = None
while proc.poll() is None:
    if pid is None:
        for p in os.listdir('/proc'):
            if p.isdigit():
                try:
                    c = open(f'/proc/{p}/cmdline', 'rb').read().split(b'\0')
                except OSError:
                    continue
                if c and c[0] == target.encode():
                    pid = int(p)
    if pid:
        try:
            for fd in os.listdir(f'/proc/{pid}/fd'):
                try:
                    t = os.readlink(f'/proc/{pid}/fd/{fd}')
                except OSError:
                    continue
                if t.startswith('/dev/dri/'):
                    dri.add(t)
        except OSError:
            pass
    time.sleep(0.2)
th.join(timeout=5)
j = subprocess.run(['journalctl', '-k', '--since', f'@{int(t0) - 5}', '--no-pager'], capture_output=True, text=True).stdout
faults = [l for l in j.splitlines() if FAULT.search(l)]
bad = [d for d in dri if 'renderD131' not in d and 'card4' not in d]
print('DEV-CHECK rc', proc.returncode, 'dri', sorted(dri), 'faults', len(faults), 'bad', bad)
if faults or bad:
    (LAB / 'HALT').write_text(json.dumps(dict(cmd=cmd, faults=faults, dri=sorted(dri)), indent=1))
    print('\n'.join(faults))
    sys.exit(9)
sys.exit(proc.returncode)
