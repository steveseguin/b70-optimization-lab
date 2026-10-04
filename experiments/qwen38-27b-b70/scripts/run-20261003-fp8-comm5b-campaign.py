#!/usr/bin/env python3
"""FP8 27B two-card collectives campaign 5b (2026-10-03): persistent gather buffers first, the one-rank step profile LAST.

Second attempt. The first (run-20261003-fp8-comm5-campaign.py) put the profile first; the profiler grew host memory
by about 0.8 GiB in a second, the research launcher's memory guard killed the container at 2.42 GiB available, the
kill logged engine-reset fault lines on card e3:00.0, and the fault latch halted the campaign before any A/B stage
(notes/2026-10-03-fp8-comm5-attempt1-guard-kill.md). Here the A/B runs first, the profile window is 8 steps instead
of 30, and the profile stage is skipped unless the host has room for it.

Preregistration: notes/2026-10-03-fp8-comm5-prereg.md. Background: notes/2026-09-18-two-card-exchange-fusion-memo.md.

Stages (one stop of the running service, one start at the end; no retry of any server):
  tp2-ag-ctl       the shipped recipe on the research launcher, strict twice: this session's control pair
  tp2-pbuf-a       candidate, overlay b70-allgather-pbuf (B70_ALLGATHER_PBUF=1): strict twice, ladder, context, quality,
                   all against the comm-2 no-MTP references the shipped recipe was gated on
  tp2-pbuf-b       a second fresh candidate server, strict twice (two-server rule)
  tp2-ag-profile   LAST and optional: the shipped recipe with the step profiler on rank 0, 8 steps. Not a speed run.
  service          health, then the two-card package service on 18124, strict vs the comm-2 no-MTP reference

The fault latch (kernel GPU fault lines) halts the campaign and skips the restore; then the user decides.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.request

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-comm5b-20261003'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
COMM2 = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917')
REF = {'strict': COMM2 / 'tp2-ag-mtp0-strict', 'ladder': COMM2 / 'tp2-ag-mtp0-ladder.json',
       'context': COMM2 / 'tp2-ag-mtp0-context/summary.json', 'quality': COMM2 / 'tp2-ag-mtp0-quality.json'}
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
SHIPPED = ['--overlay', 'b70-allgather-allreduce', '--extra-env', 'B70_ALLGATHER_ALLREDUCE=1']
PBUF = ['--overlay', 'b70-allgather-pbuf', '--extra-env', 'B70_ALLGATHER_PBUF=1']
COMMON = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows']
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]
SUITE = json.loads((ROOT / 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json').read_text())
PROMPTS = [p['prompt'] for p in SUITE['prompts'][:4]]
PROFILE_STEPS = int(os.environ.get('COMM5_PROFILE_STEPS', '8'))
PROFILE_MIN_IDLE_MIB = 13000  # the profile stage is skipped below this much idle MemAvailable
GO_GAIN = 0.010  # preregistered: candidate median must beat the control median by at least 1.0 %


def post(base, path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else b''
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read() or b'{}')


def window(base, name):
    """About 120 decode steps: the profiler overlay skips the first 40 calls and records the next 30 by itself."""
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


def server_state(srv):
    return {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}


def strict_pair(srv, name):
    r = {'server': server_state(srv)}
    if not srv.ready:
        return r
    r['strict'] = R.strict(srv.base, name, REF['strict'])
    R.save_results(); R.fault_check(SINCE)
    r['strict_run2'] = R.strict(srv.base, f'{name}-run2', REF['strict'])
    R.save_results(); R.fault_check(SINCE)
    R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')}, run2 {r['strict_run2'].get('exact')} at {r['strict_run2'].get('tok_s_1_100')}")
    return r


def full_gates(srv, name, r):
    ladder = R.ladder(srv.base, name, 2)
    r['ladder'] = R.ladder_compare(name, ladder, REF['ladder'])
    R.save_results(); R.fault_check(SINCE)
    r['context'], _ = R.context(srv.base, name, R.TP2_LENGTHS, R.TP2_MML, 2, REF['context'])
    R.save_results(); R.fault_check(SINCE)
    r['quality'], _ = R.quality(srv.base, name, 2, REF['quality'])
    R.save_results(); R.fault_check(SINCE)
    R.log(f"{name}: ladder {r['ladder'].get('verdict')}, context passed={r['context'].get('passed')}, "
          f"quality pass={r['quality'].get('pass_all')} baseline_match={r['quality'].get('baseline_match_all')}")


def exact(r, key):
    return r.get(key, {}).get('exact') == '12/12' and r.get(key, {}).get('rc') == 0


def main():
    global SINCE
    OUT.mkdir(parents=True, exist_ok=False)
    SINCE = R.now()
    R.log(f'comm-5b campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = SINCE
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(SINCE)

    # Stage 2: this session's control pair, shipped recipe on the research launcher.
    srv = R.Research('tp2-ag-ctl', 18192, COMMON + MTP5 + SHIPPED)
    results['tp2-ag-ctl'] = strict_pair(srv, 'tp2-ag-ctl')
    results['tp2-ag-ctl']['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # Stage 3: candidate, full gates.
    srv = R.Research('tp2-pbuf-a', 18193, COMMON + MTP5 + PBUF)
    r = results['tp2-pbuf-a'] = strict_pair(srv, 'tp2-pbuf-a')
    if srv.ready:
        full_gates(srv, 'tp2-pbuf-a', r)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # Stage 4: second fresh candidate server.
    srv = R.Research('tp2-pbuf-b', 18194, COMMON + MTP5 + PBUF)
    results['tp2-pbuf-b'] = strict_pair(srv, 'tp2-pbuf-b')
    results['tp2-pbuf-b']['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # Verdict, computed from the receipts by the rule written down before the run.
    def speeds(stage):
        return [results[stage][k]['tok_s_1_100'] for k in ('strict', 'strict_run2') if results[stage].get(k, {}).get('tok_s_1_100')]
    ctl, cand = speeds('tp2-ag-ctl'), speeds('tp2-pbuf-a') + speeds('tp2-pbuf-b')
    a = results['tp2-pbuf-a']
    all_exact = (all(exact(results[s], k) for s in ('tp2-pbuf-a', 'tp2-pbuf-b') for k in ('strict', 'strict_run2'))
                 and a.get('ladder', {}).get('verdict') == 'exact' and a.get('context', {}).get('passed') is True
                 and a.get('quality', {}).get('pass_all') is True and a.get('quality', {}).get('baseline_match_all') in (True, None))
    verdict = {'control_tok_s': ctl, 'candidate_tok_s': cand, 'candidate_all_exact': all_exact,
               'control_exact': all(exact(results['tp2-ag-ctl'], k) for k in ('strict', 'strict_run2')), 'go_gain': GO_GAIN}
    if len(ctl) == 2 and len(cand) == 4:
        verdict['control_median'] = statistics.median(ctl)
        verdict['candidate_median'] = statistics.median(cand)
        verdict['gain'] = verdict['candidate_median'] / verdict['control_median'] - 1
        verdict['go'] = bool(all_exact and verdict['gain'] >= GO_GAIN)
    else:
        verdict['go'] = False
        verdict['incomplete'] = True
    results['verdict'] = verdict
    R.save_results()
    R.log(f'verdict: {json.dumps(verdict)}')

    # Stage 5 (last, optional): one-rank profile of the shipped recipe. A steady two-card server leaves about 3.2 GiB of
    # host memory available and the launcher's guard kills at 2.5 GiB; an 8-step window needs roughly a quarter of the
    # 30-step one that tripped it. Skipped, not attempted, when the idle host has less than PROFILE_MIN_IDLE_MIB.
    name = 'tp2-ag-profile'
    idle_mib = int(next(l.split()[1] for l in open('/proc/meminfo') if l.startswith('MemAvailable:'))) // 1024
    if os.environ.get('COMM5_PROFILE', '1') != '1' or idle_mib < PROFILE_MIN_IDLE_MIB:
        results[name] = {'skipped': True, 'idle_mem_available_mib': idle_mib, 'needed_mib': PROFILE_MIN_IDLE_MIB}
        R.log(f'{name}: skipped (idle MemAvailable {idle_mib} MiB, need {PROFILE_MIN_IDLE_MIB})')
    else:
        profiler = ['--overlay', 'b70-step-profiler', '--extra-env', 'B70_PROFILE_DIR=/trace', '--extra-env', 'B70_PROFILE_SKIP=40',
                    '--extra-env', f'B70_PROFILE_STEPS={PROFILE_STEPS}', '--extra-env', 'B70_PROFILE_RANKS=0']
        srv = R.Research(name, 18191, COMMON + MTP5 + SHIPPED + profiler + ['--mount-dir', f'{OUT / (name + "-trace")}:/trace'])
        r = results[name] = {'server': server_state(srv), 'idle_mem_available_mib': idle_mib, 'profile_steps': PROFILE_STEPS}
        if srv.ready:
            try:
                r['window'] = window(srv.base, name)
            except Exception as exc:  # the trace is the point; a client error must not stop the campaign
                r['window'] = {'error': str(exc)}
                R.log(f'{name}: window failed: {exc}')
        r['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # Stage 6: the service back, unchanged.
    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = os.environ.get('CAMPAIGN_UNIT', 'fp8-service-comm5b')
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
        results['service']['strict'] = R.strict('http://127.0.0.1:18124', 'service', REF['strict'])
    R.save_results(); R.fault_check(SINCE)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== comm-5b campaign complete ===')


if __name__ == '__main__':
    main()
