#!/usr/bin/env python3
"""One-card long-prompt probe (2026-09-17 evening): exact continuations after 24K, 30K and 36K-token prompts.

The 32K gates ran with 2K/8K/16K prompts because the earlier corpus was too short. With the long corpus
(data/2026-09-17-long-corpus, 62K+ tokens per class, unrepeated) this campaign runs, on one card:
  tp1-mtp0-40k       R311b, no MTP, 40,960 context at 0.983: the reference continuations at
                     2048/8192/16384/24576/30720/36864 tokens, two repeats
  tp1-pkg-32k        the package `recommended` profile (32,768): 2048..30720 vs the reference
  tp1-pkg-max        the package `max-context` profile (40,960): 2048..36864 vs the reference
  service            the two-card package service back on 18124, strict vs the comm-2 no-MTP reference
One stop of the service, one start. No retry; fault latch as before. B70_FP8_TP1_IMAGE may name the local R311b tag.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-probe1-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
R.CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json'
R311B = os.environ.get('R311_IMAGE', 'sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7')
COMM2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG_ALL = '2048,8192,16384,24576,30720,36864'
LONG_32K = '2048,8192,16384,24576,30720'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'probe-1 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}; corpus {R.CORPUS}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    srv = R.Research('tp1-mtp0-40k', 18207, ['--tp', '1', '--gpu', '0', '--mem', '0.983', '--max-model-len', '40960', '--batched', '2048',
                                             '--cpu-embed', '--fa-verify-rows', '--image', R311B])
    r = results['tp1-mtp0-40k'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    ref = None
    if srv.ready:
        r['context'], ref = R.context(srv.base, 'tp1-mtp0-40k', LONG_ALL, 40960, 2)
        R.log(f"tp1-mtp0-40k: reference {r['context'].get('passed')} {r['context'].get('by_length')}")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()
    if not ref:
        raise SystemExit('no reference')

    for name, profile, port, mml, lengths in (('tp1-pkg-32k', 'recommended', 18208, 32768, LONG_32K),
                                              ('tp1-pkg-max', 'max-context', 18209, 40960, LONG_ALL)):
        pkg = R.Package(name, profile, port)
        r = results[name] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if pkg.ready:
            r['context'], _ = R.context(pkg.base, name, lengths, mml, 2, ref)
            R.log(f"{name}: context passed={r['context'].get('passed')} {r['context'].get('by_length')}")
        r['stop'] = pkg.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-probe1'
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
    R.log('=== probe-1 campaign complete ===')


if __name__ == '__main__':
    main()
