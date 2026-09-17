#!/usr/bin/env python3
"""One-card 32K promotion campaign, 2026-09-17: verify the updated one-card package (R311b image, single-checkpoint GDN
state, 32,768 context at 0.975) through its shipped launcher on all three profiles, then bring the two-card depth-5
service back. One unattended runner; one stop of the running service; one final start.

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

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-onecard-32k-20260917'))
CKPT2 = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917')  # no-MTP references at the 896-token attention block
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
    R.log(f'one-card 32K campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = since
    # The package page is 896 attention tokens per block; the no-MTP references at that block size come from ckpt-2
    # (strict outputs there were identical to the 832-block references, 12/12).
    ref = {'strict': CKPT2 / 'tp1-mtp0-b896-strict', 'ladder': CKPT2 / 'tp1-mtp0-b896-ladder.json',
           'context': CKPT2 / 'tp1-mtp0-b896-context/summary.json', 'quality': CKPT2 / 'tp1-mtp0-b896-quality.json'}
    for path in list(ref.values()) + [TP2_STRICT, PKG_TP2]:
        if not path.exists():
            raise SystemExit(f'missing: {path}')
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    pkg = R.Package('tp1-pkg-32k', 'recommended', 18130)
    r = results['tp1-pkg-32k'] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if pkg.ready:
        r['strict'] = R.strict(pkg.base, 'tp1-pkg-32k', ref['strict'])
        R.save_results(); R.fault_check(since)
        r['strict_run2'] = R.strict(pkg.base, 'tp1-pkg-32k-run2', ref['strict'])
        R.save_results(); R.fault_check(since)
        r['ladder'] = R.ladder_compare('tp1-pkg-32k', R.ladder(pkg.base, 'tp1-pkg-32k', 2), ref['ladder'])
        R.save_results(); R.fault_check(since)
        r['context'], _ = R.context(pkg.base, 'tp1-pkg-32k', LONG, 32768, 2, ref['context'])
        R.save_results(); R.fault_check(since)
        r['quality'], _ = R.quality(pkg.base, 'tp1-pkg-32k', 2, ref['quality'])
        R.save_results(); R.fault_check(since)
        r['history'] = R.history(pkg.base, 'tp1-pkg-32k')
        R.save_results(); R.fault_check(since)
        r['status_rc'] = pkg.status()
        R.log(f"tp1-pkg-32k: strict {r['strict'].get('exact')} {r['strict'].get('tok_s_1_100')} / {r['strict_run2'].get('tok_s_1_100')} tok/s, "
              f"ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}, quality {r['quality'].get('pass_all')}/{r['quality'].get('baseline_match_all')}, "
              f"history divergent={r['history'].get('divergent')}/{r['history'].get('logprob_divergent')}")
    r['stop'] = pkg.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    for name, profile, port, mml in (('tp1-pkg-max-context', 'max-context', 18131, 40960), ('tp1-pkg-no-quantization', 'no-quantization', 18132, 28672)):
        pkg = R.Package(name, profile, port)
        r = results[name] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if pkg.ready:
            r['strict'] = R.strict(pkg.base, name, ref['strict'])
            R.save_results(); R.fault_check(since)
            r['ladder'] = R.ladder_compare(name, R.ladder(pkg.base, name, 1), ref['ladder'])
            R.save_results(); R.fault_check(since)
            r['context'], _ = R.context(pkg.base, name, LONG, mml, 2, ref['context'])
            R.save_results(); R.fault_check(since)
            R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s, ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}")
        r['stop'] = pkg.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('health probe failed before the service start; service left down')
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-onecard32k'
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
    R.log('=== one-card 32K campaign complete ===')


if __name__ == '__main__':
    main()
