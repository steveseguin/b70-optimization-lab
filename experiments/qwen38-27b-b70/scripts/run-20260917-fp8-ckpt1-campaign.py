#!/usr/bin/env python3
"""FP8 27B one-card single-checkpoint GDN state campaign 1 (2026-09-17): the r311 kernel + b70-gdn-checkpoint overlay.

Stages (one stop of the running two-card service, one start at the end):
  tp1-ckpt-mtp5   one card, the shipped `recommended` settings (24,576 context, depth 5, INT4 draft shortlist, host
                  embedding, verifier rows) on the R311 image with B70_GDN_CHECKPOINT=1: strict vs the R310 one-card
                  no-MTP reference, then (only if 12/12) ladder r2, 2K/8K/16K context, chat quality, the 21-request
                  logprob replay, all vs the one-card no-MTP references
  tp1-ckpt-32k    only if every gate above is exact: the same server at 32,768 context and 0.975 memory (the point of
                  the change): strict, 2K/8K/16K vs reference, and a 30,720-token two-repeat probe (self-consistency)
  service         health, then the two-card package service on 18124, strict vs the two-card no-MTP reference

R311_IMAGE must name the image (sha256:... digest as the research launcher takes it). No retry; fault latch as before.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-ckpt1-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', '/mnt/fast-ai/bench-results/fp8-comm2-20260917/service'))
R311 = os.environ['R311_IMAGE']
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
TP1 = {'strict': R.TP1_MTP0_STRICT, 'ladder': Path('/mnt/fast-ai/bench-results/fp8-review-20260916-attempt1/tp1-mtp0-ladder.json'),
       'context': Path('/mnt/fast-ai/bench-results/fp8-followup-20260917/tp1-mtp0-long-context/summary.json'),
       'quality': REVIEW / 'tp1-mtp0-quality.json'}
TP2_STRICT = REVIEW / 'tp2-mtp0-strict'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384'
BASE = ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--batched', '2048', '--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST,
        '--cpu-embed', '--fa-verify-rows', '--overlay', 'b70-gdn-checkpoint', '--extra-env', 'B70_GDN_CHECKPOINT=1', '--image', R311]


def kv_lines(name):
    """The launcher log lines that state the KV budget and the GDN page (for the memory result)."""
    log = OUT / f'{name}-owner.log'
    if not log.exists():
        return []
    keep = re.compile(r'KV cache|kv cache|b70_gdn_checkpoint|Maximum concurrency|block size', re.I)
    return [line.strip()[:240] for line in log.read_text(errors='replace').splitlines() if keep.search(line)][:40]


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'ckpt-1 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}; image {R311}')
    results = R.RESULTS
    results['started'] = since
    results['image'] = R311
    for path in list(TP1.values()) + [TP2_STRICT]:
        if not path.exists():
            raise SystemExit(f'missing reference: {path}')
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    all_exact = False
    srv = R.Research('tp1-ckpt-mtp5', 18194, BASE + ['--max-model-len', '24576'])
    r = results['tp1-ckpt-mtp5'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}, 'kv_lines': kv_lines('tp1-ckpt-mtp5')}
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp1-ckpt-mtp5', TP1['strict'])
        R.save_results(); R.fault_check(since)
        exact = r['strict'].get('exact') == '12/12' and r['strict'].get('rc') == 0
        R.log(f"tp1-ckpt-mtp5: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
        if exact:
            r['strict_run2'] = R.strict(srv.base, 'tp1-ckpt-mtp5-run2', TP1['strict'])
            R.save_results(); R.fault_check(since)
            r['ladder'] = R.ladder_compare('tp1-ckpt-mtp5', R.ladder(srv.base, 'tp1-ckpt-mtp5', 2), TP1['ladder'])
            R.save_results(); R.fault_check(since)
            r['context'], _ = R.context(srv.base, 'tp1-ckpt-mtp5', LONG, 24576, 2, TP1['context'])
            R.save_results(); R.fault_check(since)
            r['quality'], _ = R.quality(srv.base, 'tp1-ckpt-mtp5', 2, TP1['quality'])
            R.save_results(); R.fault_check(since)
            r['history'] = R.history(srv.base, 'tp1-ckpt-mtp5')
            R.save_results(); R.fault_check(since)
            all_exact = (r['ladder'].get('verdict') == 'exact' and r['context'].get('passed') is True
                         and r['quality'].get('pass_all') is True and r['quality'].get('baseline_match_all') is True
                         and r['history'].get('rc') == 0 and not r['history'].get('divergent') and not r['history'].get('logprob_divergent'))
            R.log(f"tp1-ckpt-mtp5: ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}, quality {r['quality'].get('pass_all')}/{r['quality'].get('baseline_match_all')}, history divergent={r['history'].get('divergent')}/{r['history'].get('logprob_divergent')} -> all_exact={all_exact}")
        r['all_exact'] = all_exact
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    if all_exact:
        srv = R.Research('tp1-ckpt-32k', 18195, BASE + ['--max-model-len', '32768'])
        r = results['tp1-ckpt-32k'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}, 'kv_lines': kv_lines('tp1-ckpt-32k')}
        if srv.ready:
            r['strict'] = R.strict(srv.base, 'tp1-ckpt-32k', TP1['strict'])
            R.save_results(); R.fault_check(since)
            r['context'], _ = R.context(srv.base, 'tp1-ckpt-32k', LONG, 32768, 2, TP1['context'])
            R.save_results(); R.fault_check(since)
            r['context_30720'], _ = R.context(srv.base, 'tp1-ckpt-32k-30720', '30720', 32768, 2)
            R.save_results(); R.fault_check(since)
            R.log(f"tp1-ckpt-32k: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s, context {r['context'].get('passed')}, 30720 probe {r['context_30720'].get('passed')}")
        r['stop'] = srv.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()
    else:
        R.log('gates not exact; skipping the 32K stage')

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-ckpt1'
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
    R.log('=== ckpt-1 campaign complete ===')


if __name__ == '__main__':
    main()
