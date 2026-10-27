#!/usr/bin/env python3
import argparse, hashlib, json, statistics, subprocess, time
from pathlib import Path

ROOT = Path('/dev/shm/ownrt-lab-r0-c23gdnprefill')
RESEARCH = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/gdn-prefill-c23')
BASE = Path('/dev/shm/ownrt-lab-r0/runs/launch-bp-all.json')
DRIVER = RESEARCH / 'tp_rank0_driver.py'
BINARIES = {
    'ref': Path('/dev/shm/engine-build-svc-b19-gdnprep-20261026/sc117-engine'),
    'cand': Path('/dev/shm/engine-build-lab-r0-c23gdnprefill/sc117-engine'),
}
REF_SHA = '51f32b2655cc0a9d514081362ea6b3ceaa8b0d004df94fbbd83eb7fa76e3ae0a'
PATTERNS = ('Fault response', 'CAT error', 'engine reset', 'GPU HANG', 'wedged', 'Timedout')
MIN_AVAILABLE = 35 * 1024**3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def faults(since):
    p = subprocess.run(['journalctl', '-k', '--since', f'@{int(since)}', '--no-pager'], text=True, capture_output=True)
    return [line for line in p.stdout.splitlines() if any(x.lower() in line.lower() for x in PATTERNS)]


def available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('MemAvailable missing')


def one(name, mode):
    if (ROOT / 'HALT').exists():
        raise RuntimeError('HALT present')
    if sha(BINARIES['ref']) != REF_SHA:
        raise RuntimeError('B19 reference hash mismatch')
    avail = available()
    if avail < MIN_AVAILABLE:
        raise RuntimeError(f'35-GiB admission failed: MemAvailable={avail}')
    start = time.time()
    before = faults(start - 3600)
    if before:
        (ROOT / 'HALT').touch()
        raise RuntimeError('fault lines before run: ' + repr(before))
    launch_data = json.loads(BASE.read_text())
    for i, arg in enumerate(launch_data['argv']):
        if arg.endswith('/sc117-engine'):
            launch_data['argv'][i] = str(BINARIES[mode])
    env = launch_data['environment']
    env['FilterBdfPath'] = '0000:23:00.0'
    for key in ('OWNRT_DRAFT_ATTN_OUT', 'OWNRT_EXPERTS_V2_IQ4NL', 'OWNRT_DECODE_PROFILE'):
        env.pop(key, None)
    env['OWNRT_GDN_PREP'] = '1'
    launch = ROOT / f'launch-{name}.json'
    launch.write_text(json.dumps(launch_data, indent=1) + '\n')
    out = ROOT / 'runs' / name
    (ROOT / 'runs').mkdir(exist_ok=True)
    cmd = ['env', '-u', 'LD_PRELOAD', '-u', 'ONEAPI_DEVICE_SELECTOR', 'flock', '/dev/shm/card23gdnprefill.lock',
           'nice', '-n', '10', 'taskset', '-c', '8-15,24-31', 'python3', '-B', str(DRIVER), 'run',
           '--launch', str(launch), '--out', str(out), '--steps', '48', '--prompt', '4096', '--rows', '256',
           '--cache', str(ROOT / 'cache' / mode)]
    with (ROOT / 'runs' / f'{name}.out').open('w') as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    lines = faults(start)
    (ROOT / 'runs' / f'{name}.faults').write_text('\n'.join(lines) + ('\n' if lines else ''))
    if lines:
        (ROOT / 'HALT').touch()
        raise RuntimeError(f'GPU fault after {name}: {lines}')
    if rc:
        raise RuntimeError(f'{name} failed rc={rc}; see {out}.out')
    summary = json.loads((out / 'summary.json').read_text())
    row = dict(name=name, mode=mode, binary=sha(BINARIES[mode]), mem_available_start=avail,
               prefill_ms=summary['prefill_ms'], prompt_ms=summary['prompt_ms'],
               draft_replay_ms=summary['draft_replay_ms'], half_ms=statistics.median(summary['half_ms']),
               draft_ms=statistics.median(summary['draft_ms']), rc=rc, faults=len(lines))
    print(json.dumps(row), flush=True)
    return row


def compare(ref, cand):
    p = subprocess.run(['python3', '-B', str(DRIVER), 'compare', str(ROOT / 'runs' / ref), str(ROOT / 'runs' / cand)],
                       text=True, capture_output=True)
    text = p.stdout.strip()
    (RESEARCH / f'compare-{ref}-{cand}.json').write_text(text + '\n')
    if p.returncode:
        raise RuntimeError(f'comparison failed {ref} {cand}: {text} {p.stderr}')
    return json.loads(text)


def main(pairs):
    rows, comparisons = [], []
    for i in range(1, pairs + 1):
        order = ('ref', 'cand') if i % 2 else ('cand', 'ref')
        names = {}
        for mode in order:
            name = f'p{i}-{mode}'
            names[mode] = name
            rows.append(one(name, mode))
        comparisons.append(compare(names['ref'], names['cand']))
    result = {'rows': rows, 'comparisons': comparisons}
    for mode in ('ref', 'cand'):
        selected = [x for x in rows if x['mode'] == mode]
        for field in ('prefill_ms', 'prompt_ms', 'draft_replay_ms', 'half_ms', 'draft_ms'):
            result[f'{mode}_{field}_median'] = statistics.median(x[field] for x in selected)
    result['prefill_delta_ms'] = result['cand_prefill_ms_median'] - result['ref_prefill_ms_median']
    result['prefill_speedup_pct'] = 100 * (result['ref_prefill_ms_median'] / result['cand_prefill_ms_median'] - 1)
    result['prefill_reduction_pct'] = -100 * result['prefill_delta_ms'] / result['ref_prefill_ms_median']
    result['prompt_delta_ms'] = result['cand_prompt_ms_median'] - result['ref_prompt_ms_median']
    result['keep'] = (result['prefill_reduction_pct'] >= 5 or -result['prefill_delta_ms'] >= 500)
    (RESEARCH / 'results.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'comparisons')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', type=int, default=3)
    args = parser.parse_args()
    main(args.pairs)
