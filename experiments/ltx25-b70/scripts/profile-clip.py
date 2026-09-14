#!/usr/bin/env python3
"""One clip with existing WebSocket events; no runtime instrumentation or retries."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import time
import uuid

import aiohttp

parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('--graph', type=Path)
parser.add_argument('--server-run', type=Path)
parser.add_argument('--timeout', type=int, default=600)
args = parser.parse_args()
assert args.name and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.name)
lane = Path(__file__).resolve().parents[1]
root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
out = root / 'requests' / args.name
out.mkdir(parents=True, exist_ok=False)
graph = json.loads((args.graph or lane / 'data/baseline-api.json').read_text())
graph['414']['inputs']['run_name'] = args.name
for node, suffix in [('413', '/frame'), ('75', '/preview')]:
    if node in graph:
        graph[node]['inputs']['filename_prefix'] = args.name + suffix
(out / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
server_run = args.server_run or root
identity = json.loads((server_run / 'server-identity.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity['boot_id']
identity['proc_start_ticks'] = Path(f"/proc/{identity['pid']}/stat").read_text().split(') ')[1].split()[19]
for name in ['model-verification', 'server-args']:
    path = (root if name == 'model-verification' else server_run) / (name + '.json')
    identity[name.replace('-', '_') + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
(out / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
assert json.loads((root / 'model-verification.json').read_text())['status'] == 'passed'


async def main():
    client_id = 'ltx-profile-' + uuid.uuid4().hex
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async def call(path, payload=None):
            assert not (root / 'FAULT.json').exists(), 'device fault; halt requests'
            method = session.get if payload is None else session.post
            kwargs = {} if payload is None else {'json': payload}
            async with method('http://127.0.0.1:8188' + path, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

        queue = await call('/queue')
        assert not queue['queue_running'] and not queue['queue_pending']
        async with session.ws_connect('http://127.0.0.1:8188/ws?clientId=' + client_id) as ws:
            await ws.receive_json(timeout=10)
            start = time.monotonic()
            submission = await call('/prompt', {'prompt': graph, 'client_id': client_id})
            (out / 'submission.json').write_text(json.dumps(submission, indent=2) + '\n')
            assert not submission.get('node_errors'), submission
            prompt_id = submission['prompt_id']
            print('submitted', prompt_id, flush=True)
            events = []
            with (out / 'events.jsonl').open('x') as log:
                while time.monotonic() - start < args.timeout:
                    assert not (root / 'FAULT.json').exists(), 'fault recorded; no further requests'
                    try:
                        message = await ws.receive(timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    if message.type == aiohttp.WSMsgType.TEXT:
                        event = message.json()
                        if event.get('data', {}).get('prompt_id') != prompt_id:
                            continue
                        row = {'seconds': time.monotonic() - start, **event}
                        events.append(row)
                        log.write(json.dumps(row) + '\n')
                        log.flush()
                        if event['type'] in ['execution_success', 'execution_error', 'execution_interrupted']:
                            break
                    elif message.type in [aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED]:
                        raise RuntimeError('WebSocket disconnected; inspect active job, do not retry')
                else:
                    raise TimeoutError('client deadline; inspect active job, do not retry')
            for _ in range(30):
                history = await call('/history/' + prompt_id)
                if prompt_id in history:
                    break
                await asyncio.sleep(0.1)
            row = history[prompt_id]
            (out / 'history.json').write_text(json.dumps(row, indent=2) + '\n')
            result = {'name': args.name, 'prompt_id': prompt_id, 'seconds': time.monotonic() - start,
                      'status': row['status']}
            (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            starts = [e for e in events if e['type'] == 'executing' and e['data'].get('node')]
            timings = []
            for i, event in enumerate(starts):
                node = event['data']['node']
                end = starts[i + 1]['seconds'] if i + 1 < len(starts) else events[-1]['seconds']
                timings.append({'node': node, 'class_type': graph[node]['class_type'],
                                'start_seconds': event['seconds'], 'seconds': end - event['seconds']})
            profile = {'definition': 'client-received node-start event intervals; approximate wall time, not synchronized kernel timings',
                       'prompt_id': prompt_id, 'seconds': result['seconds'], 'nodes': timings}
            for node, key in [('75', 'preview_ready_seconds'), ('414', 'tensor_archive_ready_seconds')]:
                ready = [e['seconds'] for e in events if e['type'] == 'executed' and e['data'].get('node') == node]
                profile[key] = ready[0] if ready else None
            (out / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
            print(json.dumps(profile, indent=2), flush=True)
            assert row['status']['status_str'] == 'success', 'generation failed; preserve evidence'
            assert not any(m[1].get('nodes') for m in row['status']['messages'] if m[0] == 'execution_cached')


asyncio.run(main())
