#!/usr/bin/env python3
"""Submit exactly one generation; failures never restart or retry the server."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('--timeout', type=int, default=3600)
args = parser.parse_args()
if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.name):
    parser.error('use lowercase identifier')
lane = Path(__file__).resolve().parents[1]
evidence = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
out = evidence / 'requests' / args.name
out.mkdir(parents=True, exist_ok=False)
assert json.loads((evidence / 'model-verification.json').read_text())['status'] == 'passed'
identity = json.loads((evidence / 'server-identity.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity['boot_id']
assert Path(f"/proc/{identity['pid']}/cmdline").exists(), 'original server is no longer running'
identity['proc_start_ticks'] = Path(f"/proc/{identity['pid']}/stat").read_text().split(') ')[1].split()[19]
identity['model_verification_sha256'] = hashlib.sha256((evidence / 'model-verification.json').read_bytes()).hexdigest()
(out / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')

def call(path, payload=None):
    if (evidence / 'FAULT.json').exists():
        raise RuntimeError('device fault latch set; no new requests allowed')
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request('http://127.0.0.1:8188' + path, data=data,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'another request is active'
graph = json.loads((lane / 'data/baseline-api.json').read_text())
graph['414']['inputs']['run_name'] = args.name
graph['413']['inputs']['filename_prefix'] = args.name + '/frame'
graph['75']['inputs']['filename_prefix'] = args.name + '/preview'
(out / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
start = time.monotonic()
response = call('/prompt', {'prompt': graph, 'client_id': 'ltx25-baseline'})
(out / 'submission.json').write_text(json.dumps(response, indent=2) + '\n')
assert not response.get('node_errors'), response
pid = response['prompt_id']
print('submitted', pid, flush=True)
while time.monotonic() - start < args.timeout:
    history = call('/history/' + pid)
    if pid in history:
        row = history[pid]
        (out / 'history.json').write_text(json.dumps(row, indent=2) + '\n')
        summary = {'name': args.name, 'prompt_id': pid, 'seconds': time.monotonic() - start,
                   'status': row['status']}
        (out / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary), flush=True)
        assert row['status']['status_str'] == 'success', 'generation failed; inspect saved history'
        cached = [m[1].get('nodes', []) for m in row['status']['messages'] if m[0] == 'execution_cached']
        assert not any(cached), ('node cache unexpectedly used', cached)
        break
    time.sleep(5)
else:
    (out / 'timeout.json').write_text(json.dumps({'prompt_id': pid, 'seconds': args.timeout}))
    raise TimeoutError('client deadline; do not retry or restart the server; inspect the active job')
