#!/usr/bin/env python3
"""One-card 24K promotion campaign, 2026-09-17: verify the updated one-card package (24,576 context, 2,048-token
prefill chunk) through its shipped launcher, probe the no-quantization profile at a longer context, then bring the
two-card depth-5 service back. One unattended runner; one stop of the running service; one final start.

Stages:
  tp1-pkg-24k              `serve.py start --profile recommended` (24,576 context): strict vs the R310 no-MTP strict
                           run, 64-prompt oracle + two queued passes vs the one-card no-MTP ladder, 2K/8K/16K context
                           screen vs tp1-mtp0-long, chat quality vs the review no-MTP baseline, 21-request logprob
                           replay, status, clean stop
  tp1-nq-20k-b2048         research probe: FP16 draft shortlist (no-quantization) at 20,480 context, 2,048 chunk;
                           strict + oracle if it reaches ready
  service                  health probe, then the two-card package service (depth 5) on 18124 in its own unit,
                           strict parity vs the same-image no-MTP reference
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-onecard-24k-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
FOLLOWUP = Path('/mnt/fast-ai/bench-results/fp8-followup-20260917')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', str(FOLLOWUP / 'service')))
TP1_LADDER = Path('/mnt/fast-ai/bench-results/fp8-review-20260916-attempt1/tp1-mtp0-ladder.json')
TP1_CTX = FOLLOWUP / 'tp1-mtp0-long-context/summary.json'
TP1_QUALITY = REVIEW / 'tp1-mtp0-quality.json'
TP2_STRICT = REVIEW / 'tp2-mtp0-strict'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'one-card 24K campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    for path in (TP1_LADDER, TP1_CTX, TP1_QUALITY, TP2_STRICT, PKG_TP2):
        if not path.exists():
            raise RuntimeError(f'missing {path}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        R.log('preflight health probe failed; halting before any server')
        raise SystemExit(4)
    R.fault_check(since)

    pkg = R.Package('tp1-pkg-24k', 'recommended', 18130)
    r = results['tp1-pkg-24k'] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if pkg.ready:
        r['strict'] = R.strict(pkg.base, 'tp1-pkg-24k', R.TP1_MTP0_STRICT)
        r['ladder'] = R.ladder_compare('tp1-pkg-24k', R.ladder(pkg.base, 'tp1-pkg-24k', 2), TP1_LADDER)
        r['context'], _ = R.context(pkg.base, 'tp1-pkg-24k', LONG, 24576, 2, TP1_CTX)
        r['quality'], _ = R.quality(pkg.base, 'tp1-pkg-24k', 2, TP1_QUALITY)
        r['history'] = R.history(pkg.base, 'tp1-pkg-24k')
        r['status_rc'] = pkg.status()
    r['stop'] = pkg.stop()
    if (pkg.out / 'server.log').exists():
        r['memory_lines'] = [line.strip()[-160:] for line in (pkg.out / 'server.log').read_text(errors='replace').splitlines()
                             if 'KV cache' in line or 'Actual usage' in line][-4:]
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    srv = R.Research('tp1-nq-20k-b2048', 18133, ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--max-model-len', '20480',
                                                 '--batched', '2048', '--cpu-embed', '--fa-verify-rows', '--mtp', '5',
                                                 '--draft-fp16-shortlist', R.SHORTLIST])
    r = results['tp1-nq-20k-b2048'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp1-nq-20k-b2048', R.TP1_MTP0_STRICT)
        r['ladder'] = R.ladder_compare('tp1-nq-20k-b2048', R.ladder(srv.base, 'tp1-nq-20k-b2048', 1), TP1_LADDER)
    r['stop'] = srv.stop()
    r['memory_log'] = [line for line in json.loads((srv.out / 'state.json').read_text()).get('memory_log', [])
                       if any(k in line for k in ('KV cache', 'Actual usage', 'ValueError', 'larger than'))][-6:]
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('health probe failed before the service start; service left down')
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917b'
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
    R.log('=== one-card 24K campaign complete ===')


if __name__ == '__main__':
    main()
