import subprocess, sys, time, json
from pathlib import Path
SD = Path(sys.argv[0]).parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PY = '/home/steve/.venvs/ltx25-baseline/bin/python'
name = sys.argv[1]; pid = sys.argv[2]
raw = SD / f'{name}-spy.raw'
spy = subprocess.Popen(['/home/steve/.local/bin/py-spy', 'record', '--pid', pid,
                        '--duration', '9', '--rate', '200', '--idle', '--nonblocking',
                        '--format', 'raw', '--output', str(raw)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(1.0)
clip = subprocess.run([PY, '-B', str(SD / 'control_clip_cpu.py'), name, '--pid', pid,
                       '--server-run', str(ROOT / 'encoder-server-host-embedding-13'),
                       '--out', str(SD / 'cpu-probe')], capture_output=True, text=True, timeout=900)
so, se = spy.communicate(timeout=120)
print('spy_rc', spy.returncode, se[-400:] if se else '')
print('clip_rc', clip.returncode)
if clip.returncode == 0:
    d = json.loads(clip.stdout)
    print(json.dumps({k: d[k] for k in ('run','preview_ready_seconds','sampler_wall_s','sampler_cpu_per_wall','parity_status','bitwise_all_equal')}))
else:
    print(clip.stdout[-1500:], clip.stderr[-1500:])
