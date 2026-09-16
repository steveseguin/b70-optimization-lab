#!/usr/bin/env python3
"""Run one control clip via the frozen profile-clip.py while sampling the
server process's CPU time. Read-only observation of /proc; no GPU calls,
no instrumentation inside the server, no retries."""
import argparse, json, subprocess, sys, threading, time
from pathlib import Path

LANE = Path('/home/steve/llm-optimizations/experiments/ltx25-b70')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PY = '/home/steve/.venvs/ltx25-baseline/bin/python'
HZ = float(subprocess.check_output(['getconf', 'CLK_TCK'], text=True).strip())

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--pid', type=int, required=True)
ap.add_argument('--server-run', required=True)
ap.add_argument('--reference', default='baseline-01')
ap.add_argument('--interval', type=float, default=0.02)
ap.add_argument('--out', required=True)
ap.add_argument('--graph', required=True)
ap.add_argument('--mode', required=True)
ap.add_argument('--clip-index', type=int, default=0)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

# Control graph: exactly the validated screen-02 control arm, run names retargeted.
base = json.loads((Path(a.graph)).read_text())
assert base['420']['inputs'] == {'placement': 'split', 'encoder_mode': 'control'}
assert base['422']['inputs']['mode'] == a.mode and base['422']['inputs']['selection'] == 'all48'
base['422']['inputs']['run_name'] = a.name
# Set run_name on EVERY node that takes one. Naming them individually meant a
# newly added gate kept its default and its receipt collided on the second clip.
for _node in base.values():
    if 'run_name' in _node.get('inputs', {}):
        _node['inputs']['run_name'] = a.name
    if 'clip_index' in _node.get('inputs', {}):
        _node['inputs']['clip_index'] = a.clip_index
# The generic loop above already set run_name on every node that has one. These
# two were named explicitly before that loop existed; keep them as assertions
# rather than assignments, because a cached arm has no placement node at all.
for _legacy in ('421', '414'):
    if _legacy in base:
        assert base[_legacy]['inputs']['run_name'] == a.name
base['75']['inputs']['filename_prefix'] = a.name + '/preview'
graph_path = out / (a.name + '-graph.json')
graph_path.write_text(json.dumps(base, indent=2) + '\n')

samples, stop = [], threading.Event()
stat_path = Path(f'/proc/{a.pid}/stat')
task_dir = Path(f'/proc/{a.pid}/task')

def sample():
    while not stop.is_set():
        try:
            f = stat_path.read_text().split(') ')[1].split()
            utime, stime = int(f[11]), int(f[12])
            threads = {}
            for t in task_dir.iterdir():
                try:
                    tf = (t / 'stat').read_text().split(') ')[1].split()
                    tu = (int(tf[11]) + int(tf[12])) / HZ
                    if tu > 0:
                        threads[t.name] = tu
                except (OSError, IndexError):
                    pass
            samples.append({'t': time.time(), 'cpu': (utime + stime) / HZ, 'threads': threads})
        except (OSError, IndexError):
            pass
        stop.wait(a.interval)

thread = threading.Thread(target=sample, daemon=True)
thread.start()
t_launch = time.time()
proc = subprocess.run([PY, '-B', str(LANE / 'scripts/profile-clip.py'), a.name,
                       '--graph', str(graph_path), '--server-run', str(a.server_run)],
                      capture_output=True, text=True, timeout=900)
t_done = time.time()
stop.set(); thread.join(timeout=5)
(out / (a.name + '-clip.log')).write_text(proc.stdout + '\n--- stderr ---\n' + proc.stderr)
(out / (a.name + '-cpu-samples.json')).write_text(json.dumps(
    {'pid': a.pid, 'clk_tck': HZ, 'interval_s': a.interval, 'launch_wall': t_launch,
     'done_wall': t_done, 'returncode': proc.returncode, 'samples': samples}))
if proc.returncode != 0:
    print(json.dumps({'run': a.name, 'status': 'clip-failed', 'rc': proc.returncode,
                      'stderr': proc.stderr[-2000:]}))
    sys.exit(1)

profile = json.loads((ROOT / 'requests' / a.name / 'profile.json').read_text())
sub_wall = (ROOT / 'requests' / a.name / 'submission.json').stat().st_mtime

def cpu_between(t0, t1):
    """CPU core-seconds consumed in [t0, t1] wall seconds relative to submission."""
    lo = [s for s in samples if s['t'] <= sub_wall + t0]
    hi = [s for s in samples if s['t'] <= sub_wall + t1]
    if not lo or not hi:
        return None
    return round(hi[-1]['cpu'] - lo[-1]['cpu'], 4)

rows = []
for n in profile['nodes']:
    w = n['seconds']
    c = cpu_between(n['start_seconds'], n['start_seconds'] + w)
    rows.append({'node': n['node'], 'class_type': n['class_type'], 'wall_s': round(w, 4),
                 'cpu_core_s': c, 'cpu_per_wall': round(c / w, 3) if c is not None and w > 0 else None})
sampler = [r for r in rows if r['node'] in ('344', '368')]
summary = {'run': a.name, 'preview_ready_seconds': profile['preview_ready_seconds'],
           'total_seconds': profile['seconds'], 'nodes': rows,
           'sampler_wall_s': round(sum(r['wall_s'] for r in sampler), 4),
           'sampler_cpu_core_s': round(sum(r['cpu_core_s'] for r in sampler), 4) if all(r['cpu_core_s'] is not None for r in sampler) else None}
summary['sampler_cpu_per_wall'] = round(summary['sampler_cpu_core_s'] / summary['sampler_wall_s'], 3) if summary['sampler_cpu_core_s'] else None

cmp_path = out / (a.name + '-parity.json')
cp = subprocess.run([PY, '-B', str(LANE / 'scripts/compare-clip.py'), a.reference, a.name,
                     '--output', str(cmp_path)], capture_output=True, text=True, timeout=300)
parity = json.loads(cmp_path.read_text()) if cmp_path.exists() else {'status': 'missing', 'stderr': cp.stderr[-1500:]}
summary['parity_status'] = parity.get('status')
summary['bitwise_all_equal'] = all(v.get('bitwise_equal') is True for v in parity.get('comparisons', {}).values()) if parity.get('comparisons') else False
summary['comparisons'] = sorted(parity.get('comparisons', {}))
(out / (a.name + '-summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
