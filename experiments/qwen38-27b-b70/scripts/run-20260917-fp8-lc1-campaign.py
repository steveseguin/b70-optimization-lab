#!/usr/bin/env python3
"""One-card long-context campaign 1 (2026-09-17 night): where the writing speed goes after 24K+ prompts, and 43K probes.

Stages (one stop of the service, one start):
  tp1-prof       R311b checkpoint recipe at 40,960 with the step profiler in per-prefill mode: one 16,384-, one
                 24,576- and one 32,768-token prompt (prose from the long corpus) with 200-token answers; the overlay
                 writes a 30-step decode trace per prompt, summarised by analyze-decode-trace.py after the stop
  tp1-mtp0-46k   R311b, no MTP, 46,080 context at 0.983: reference continuations at 30,720 / 36,864 / 43,008
  tp1-ck-46k     R311b + checkpoint, depth 5, 46,080 at 0.983: strict vs the 896 no-MTP reference, 2K/8K/16K vs the
                 ckpt-2 references, 30,720 / 36,864 / 43,008 vs the stage above (the context ceiling probe)
  service        the two-card package service back on 18124, strict vs the comm-2 no-MTP reference
No retry; fault latch as before.
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

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-lc1-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
R.CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json'
R311B = os.environ.get('R311_IMAGE', 'sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7')
CKPT2 = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917')
COMM2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
ANALYZE = ROOT / 'experiments/qwen38-27b-b70/scripts/analyze-decode-trace.py'
BASE = ['--tp', '1', '--gpu', '0', '--batched', '2048', '--cpu-embed', '--fa-verify-rows', '--image', R311B]
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]
CK = ['--overlay', 'b70-gdn-checkpoint', '--extra-env', 'B70_GDN_CHECKPOINT=1']
LONG_HI = '30720,36864,43008'


def post(base, path, body, timeout=1800):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def profile_requests(base):
    corpus = json.loads(R.CORPUS.read_text())
    prose = next(s['text'] for s in corpus['sources'] if s['label'] == 'prose')
    ids = post(base, '/tokenize', {'model': R.MODEL_NAME, 'prompt': prose, 'add_special_tokens': False})['tokens']
    out = {'available_tokens': len(ids), 'requests': []}
    post(base, '/v1/completions', {'model': R.MODEL_NAME, 'prompt': ids[:512], 'max_tokens': 32, 'temperature': 0})
    for length in (16384, 24576, 32768):
        started = time.monotonic()
        result = post(base, '/v1/completions', {'model': R.MODEL_NAME, 'prompt': ids[:length], 'max_tokens': 200, 'temperature': 0, 'ignore_eos': True})
        out['requests'].append({'prompt_tokens': length, 'completion_tokens': result['usage']['completion_tokens'],
                                'wall_s': time.monotonic() - started, 'text_sha256': R.sha(result['choices'][0]['text'].encode()) if hasattr(R, 'sha') else None})
        R.log(f'profile request {length}: {result["usage"]["completion_tokens"]} tokens in {out["requests"][-1]["wall_s"]:.1f}s')
        time.sleep(5)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'lc-1 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    trace_dir = OUT / 'prof-trace'
    trace_dir.mkdir()
    srv = R.Research('tp1-prof', 18215, BASE + MTP5 + CK + ['--mem', '0.983', '--max-model-len', '40960', '--overlay', 'b70-step-profiler',
                                                          '--extra-env', 'B70_PROFILE_DIR=/trace', '--extra-env', 'B70_PROFILE_BY_PREFILL=1',
                                                          '--extra-env', 'B70_PROFILE_STEPS=30', '--mount-dir', f'{trace_dir}:/trace'])
    r = results['tp1-prof'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        try:
            r['requests'] = profile_requests(srv.base)
        except Exception as exc:
            r['requests'] = {'error': str(exc)}
            R.log(f'profile requests failed: {exc}')
        time.sleep(20)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()
    r['traces'] = {}
    for trace in sorted(trace_dir.glob('*.json')):
        if trace.name.endswith('.meta.json'):
            continue
        summary = OUT / f'prof-{trace.stem}-summary.json'
        rc = R.sh([sys.executable, ANALYZE, trace, '--top', '20', '--out', summary], f'analyze-{trace.stem}', 1800)
        if summary.exists():
            s = json.loads(summary.read_text())
            r['traces'][trace.stem] = {'wall_ms': s['wall_ms'], 'device_busy_ms': s['device_busy_ms'], 'steps': s['steps'].get('count'),
                                       'top': [(t['name'][:60], round(t['total_ms'], 1), t['count']) for t in s['top_kernels'][:8]]}
            R.log(f"{trace.stem}: wall {s['wall_ms']:.0f} ms, busy {s['device_busy_ms']:.0f} ms, steps {s['steps'].get('count')}")
    R.save_results()

    srv = R.Research('tp1-mtp0-46k', 18216, BASE + ['--mem', '0.983', '--max-model-len', '46080'])
    r = results['tp1-mtp0-46k'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    ref = None
    if srv.ready:
        r['context'], ref = R.context(srv.base, 'tp1-mtp0-46k', LONG_HI, 46080, 2)
        R.log(f"tp1-mtp0-46k: reference {r['context'].get('passed')} {r['context'].get('by_length')}")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    srv = R.Research('tp1-ck-46k', 18217, BASE + MTP5 + CK + ['--mem', '0.983', '--max-model-len', '46080'])
    r = results['tp1-ck-46k'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp1-ck-46k', CKPT2 / 'tp1-mtp0-b896-strict')
        R.save_results(); R.fault_check(since)
        r['context_short'], _ = R.context(srv.base, 'tp1-ck-46k-short', R.TP2_LENGTHS, 46080, 2, CKPT2 / 'tp1-mtp0-b896-context/summary.json')
        R.save_results(); R.fault_check(since)
        if ref:
            r['context_long'], _ = R.context(srv.base, 'tp1-ck-46k-long', LONG_HI, 46080, 2, ref)
        R.log(f"tp1-ck-46k: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s, short {r['context_short'].get('passed')}, long {r.get('context_long', {}).get('passed')} {r.get('context_long', {}).get('by_length')}")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-lc1'
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
        results['service']['strict'] = R.strict('http://127.0.0.1:18124', 'service', COMM2_STRICT)
    R.save_results(); R.fault_check(since)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== lc-1 campaign complete ===')


if __name__ == '__main__':
    main()
