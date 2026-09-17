#!/usr/bin/env python3
"""FP8 27B decode-step profile campaign 3, 2026-09-17: in-worker torch/XPU profiler (b70-step-profiler overlay) per topology, then the service back.

Stages:
  tp1-profile   one card, the shipped `recommended` settings (24,576 context, 2,048 chunk, depth 5, shortlist, host
                embedding, verifier rows) with `--profiler-config.profiler=torch`: warm-up prompt, then a profiler
                window over four 128-token completions (POST /start_profile ... /stop_profile), trace under <out>/trace
  tp2-profile   two cards, the shipped depth-5 settings, same window
  service       health, then the two-card package service on 18124, strict parity vs the same-image no-MTP reference

Owns one stop of the running service and one start at the end. No retry; fault latch as before.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-profile3-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', '/mnt/fast-ai/bench-results/fp8-profile2-20260917/service'))
TP2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict')
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
SUITE = json.loads((ROOT / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json').read_text())
PROMPTS = [p['prompt'] for p in SUITE['prompts'][:4]]


def post(base, path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else b''
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read() or b'{}')


def window(base, name):
    """Drive about 120 decode steps: the overlay skips the first 40 calls and profiles the next 60 by itself."""
    result = {'prompts': len(PROMPTS)}
    started = time.monotonic()
    tokens = 0
    for prompt in PROMPTS:
        out = post(base, '/v1/completions', {'model': R.MODEL_NAME, 'prompt': prompt, 'max_tokens': 128, 'temperature': 0, 'ignore_eos': True})
        tokens += out['usage']['completion_tokens']
    result['window_seconds'] = time.monotonic() - started
    result['completion_tokens'] = tokens
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        traces = sorted((OUT / f'{name}-trace').glob('worker-*.json'))
        if traces and all(time.time() - t.stat().st_mtime > 10 for t in traces):
            break
        time.sleep(5)
    traces = sorted((OUT / f'{name}-trace').glob('worker-*'))
    result['traces'] = [str(t) for t in traces]
    result['trace_bytes'] = sum(t.stat().st_size for t in traces)
    R.log(f'{name}: {tokens} tokens in {result["window_seconds"]:.1f}s, {len(traces)} trace file(s), {result["trace_bytes"] / 2**20:.1f} MiB')
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'profile campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    profiler = ['--overlay', 'b70-step-profiler', '--extra-env', 'B70_PROFILE_DIR=/trace', '--extra-env', 'B70_PROFILE_SKIP=40', '--extra-env', 'B70_PROFILE_STEPS=60']
    for name, port, args in (
        ('tp1-profile', 18190, ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--max-model-len', '24576', '--batched', '2048', '--mtp', '5',
                                '--draft-int4', '--shortlist', R.SHORTLIST, '--cpu-embed', '--fa-verify-rows']),
        ('tp2-profile', 18191, ['--tp', '2', '--mem', '0.95', '--max-model-len', '33024', '--batched', '4096', '--mtp', '5',
                                '--draft-int4', '--shortlist', R.SHORTLIST, '--fa-verify-rows'])):
        srv = R.Research(name, port, args + profiler + ['--mount-dir', f'{OUT / (name + "-trace")}:/trace'])
        r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            try:
                r['window'] = window(srv.base, name)
            except Exception as exc:  # the trace is the point; a client error must not stop the campaign
                r['window'] = {'error': str(exc)}
                R.log(f'{name}: window failed: {exc}')
        r['stop'] = srv.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917i'
    argv = ['systemd-run', '--user', '--unit', unit, '--working-directory', str(ROOT), '--collect',
            sys.executable, str(PKG_TP2), 'start', '--model-dir', str(R.MODEL), '--state-dir', str(state_dir), '--port', '18124']
    R.wait_port_free(18124)
    (OUT / 'service.command.json').write_text(json.dumps({'argv': argv, 'started': R.now()}) + '\n')
    subprocess.run(argv, check=True)
    deadline = time.monotonic() + 2400
    state = {}
    while time.monotonic() < deadline:
        if (state_dir / 'state.json').exists():
            state = json.loads((state_dir / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        time.sleep(10)
    results['service'] = {'status': state.get('status'), 'error': state.get('error'), 'unit': unit, 'state_dir': str(state_dir)}
    R.log(f'service: {state.get("status")} {state.get("error") or ""}')
    if state.get('status') == 'ready':
        results['service']['strict'] = R.strict('http://127.0.0.1:18124', 'service', TP2_STRICT)
    R.save_results(); R.fault_check(since)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== profile campaign complete ===')


if __name__ == '__main__':
    main()
