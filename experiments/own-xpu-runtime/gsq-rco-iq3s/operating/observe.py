#!/usr/bin/env python3
"""Passive host evidence only: no device API, service mutation or settings writes."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
UNITS = ('qwen38-27b-fp8', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision')


def process_identity(pid):
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return dict(start_ticks=int(fields[19]), state=fields[0])


def target_nodes(snapshot, bdf):
    nodes = {name: row for name, row in snapshot['drm'].items() if row['bdf'] == bdf}
    if not any(n.startswith('card') for n in nodes) or not any(n.startswith('renderD') for n in nodes):
        raise RuntimeError('target primary/render aliases incomplete')
    if any(r['driver'] != 'xe' or not re.fullmatch(r'\d+:\d+', r['dev']) for r in nodes.values()):
        raise RuntimeError('target device mapping invalid')
    return nodes


def command(argv):
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    if p.returncode or p.stderr.strip():
        raise RuntimeError('passive command failed: ' + argv[0])
    return p.stdout


def observe():
    row = dict(utc=datetime.now(timezone.utc).isoformat(), metadata_only=True,
               device_api_calls=0, device_opens=0, service_changes=0)
    row['boot'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    row['root_free_bytes'] = shutil.disk_usage(ROOT).free
    row['memory'] = {k: int(v.split()[0])*1024 for k, v in
                     (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
                     if k in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree')}
    row['units'] = {}
    for unit in UNITS:
        text = command(['systemctl', '--user', 'show', unit+'.service',
                        '--property=Id,MainPID,ActiveState,SubState,Restart,SendSIGKILL,TimeoutStopUSec,KillMode'])
        row['units'][unit] = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    row['drm'] = {}
    for node in Path('/sys/class/drm').iterdir():
        if re.fullmatch(r'(card\d+|renderD\d+)', node.name) and (node/'device/vendor').read_text().strip() == '0x8086':
            row['drm'][node.name] = dict(bdf=(node/'device').resolve().name,
                dev=(node/'dev').read_text().strip(), driver=(node/'device/driver').resolve().name)
    helper = ROOT/'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py'
    row['passive_helper_sha256'] = hashlib.sha256(helper.read_bytes()).hexdigest()
    # Bind PID identities on both sides of the descriptor scan. A disappearing
    # or newly appearing process makes this sample inconclusive, never empty.
    pre_identities = {}
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:
                pre_identities[proc.name] = process_identity(proc.name)
            except (OSError, ValueError, IndexError):
                pre_identities[proc.name] = None
    # Only this read-only /proc inventory needs privilege; credential never enters argv/output.
    with Path('/home/steve/SUDOPASSWORD.txt').open('rb') as credential:
        p = subprocess.run(['/usr/bin/sudo', '-S', '-p', '', '--', '/usr/bin/python3', '-B', str(helper)],
                           stdin=credential, capture_output=True, text=True, timeout=30)
    if p.returncode not in (0, 1) or p.stderr.strip():
        raise RuntimeError('privileged passive inventory failed')
    row['inventory'] = json.loads(p.stdout)
    if row['inventory']['errors'] or not row['inventory']['metadata_only'] or row['inventory']['device_opens']:
        raise RuntimeError('incomplete passive inventory')
    row['holders'] = {}
    row['identity_races'] = []
    for holder in row['inventory']['holders']:
        pid = holder['pid']
        identity = process_identity(pid)
        prior = pre_identities.get(str(pid))
        if identity is None or prior is None or identity['start_ticks'] != prior['start_ticks']:
            row['identity_races'].append(pid)
        row['holders'][str(pid)] = identity
    driver = ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'
    patterns = {}
    for node in ast.parse(driver.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                    patterns[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
    assert set(patterns) == {'FAULT', 'DELETED'}
    raw = command(['/usr/bin/journalctl', '-k', '-b', '--no-pager', '-o', 'json'])
    journal = [json.loads(line) for line in raw.splitlines()]
    assert journal and all(x.get('_BOOT_ID') == row['boot'].replace('-', '') for x in journal)
    row['kernel'] = dict(journal_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                        rows=len(journal), last_cursor=journal[-1]['__CURSOR'], faults=[])
    for x in journal:
        for line in str(x.get('MESSAGE', '')).splitlines():
            if patterns['FAULT'].search(line) and not patterns['DELETED'].search(line):
                row['kernel']['faults'].append(dict(message=line, timestamp=x.get('__MONOTONIC_TIMESTAMP')))
    baseline = json.loads((HERE/'host-before-stop.json').read_text())
    row['known_fault_baseline_matches'] = (row['boot'] == baseline['boot']
        and row['kernel']['faults'] == baseline['kernel']['faults'])
    queue = ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
    row['queue'] = {}
    for lane in ('A', 'B'):
        row['queue'][lane] = {name: (queue/f'{name}-{lane}{suffix}').read_text() if (queue/f'{name}-{lane}{suffix}').exists() else None
                             for name, suffix in [('PAUSE', ''), ('STOP', ''), ('queue', '.txt'), ('inflight', '.json')]}
    row['endpoints'] = {}
    for port in (18130, 18131):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics', timeout=10) as response:
                text = response.read(1024*1024).decode()
            metrics = {}
            for metric in ('num_requests_running', 'num_requests_waiting'):
                metrics[metric] = [float(m[1]) for line in text.splitlines() if
                    (m := re.match(r'^vllm:'+metric+r'(?:\{[^}]*\})?\s+([0-9.eE+-]+)', line))]
            row['endpoints'][str(port)] = metrics
        except (OSError, ValueError) as ex:
            row['endpoints'][str(port)] = {'unavailable': type(ex).__name__}
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = observe()
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'output': str(args.output), 'known_fault_baseline_matches': result['known_fault_baseline_matches'],
                      'holder_pids': list(result['holders']), 'service_changes': 0}))
