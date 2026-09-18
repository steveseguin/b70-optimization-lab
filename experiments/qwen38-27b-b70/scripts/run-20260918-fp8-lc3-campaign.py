#!/usr/bin/env python3
"""One-card long-context campaign 3 (2026-09-18): the one-pass verifier attention on the r312c image (upstream attention untouched), gated against the R311b references.

Stages (one stop of the service, one start):
  tp1-r312-mtp0    R312b image, no MTP, 32,768 at 0.983: strict vs the R311b 896 no-MTP reference (does the rebuilt
                   attention library reproduce the upstream one bit for bit?), then the R312 references: ladder r2,
                   the long-corpus screen at 2K/8K/16K/24K/30K (two repeats), chat quality
  tp1-r312-multiq  R312b + single-checkpoint state + one-pass verifier (b70-fa-multiq, v_tile 64), depth 5, INT4
                   shortlist, host embedding, 32,768 at 0.975: strict twice, ladder r2, the same long screen, quality,
                   the 21-request logprob replay, all vs the R312 references; the writing speed after long prompts is
                   the number to compare with R311b (66 tok/s after 16K, 40 after 24K)
  service          the two-card package service back on 18124, strict vs the comm-2 no-MTP reference
No retry; fault latch as before. R312_IMAGE names the image id.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-lc3-20260918'))
CKPT2 = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917')
REF5 = Path('/mnt/fast-ai/bench-results/fp8-probe1-20260917/tp1-mtp0-40k-context-5lengths/summary.json')
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
LONG_CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json'
AMD_CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json'  # the ckpt2 context baseline's corpus
R.CORPUS = LONG_CORPUS
R312 = os.environ['R312_IMAGE']
CKPT2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/tp1-mtp0-b896-strict')
COMM2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384,24576,30720'
BASE = ['--tp', '1', '--gpu', '0', '--batched', '2048', '--cpu-embed', '--image', R312]
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]
CK = ['--overlay', 'b70-gdn-checkpoint', '--extra-env', 'B70_GDN_CHECKPOINT=1']
MQ = ['--overlay', 'b70-fa-multiq', '--extra-env', 'B70_FA_MULTIQ=1']


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'lc-3 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}; image {R312}')
    results = R.RESULTS
    results['started'] = since
    ref = {'strict': CKPT2 / 'tp1-mtp0-b896-strict', 'ladder': CKPT2 / 'tp1-mtp0-b896-ladder.json',
           'context': CKPT2 / 'tp1-mtp0-b896-context/summary.json', 'quality': CKPT2 / 'tp1-mtp0-b896-quality.json', 'long': REF5}
    for path in ref.values():
        if not path.exists():
            raise SystemExit(f'missing reference: {path}')
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    srv = R.Research('tp1-r312c-multiq', 18220, BASE + MTP5 + CK + MQ + ['--mem', '0.975', '--max-model-len', '32768'])
    r = results['tp1-r312c-multiq'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp1-r312c-multiq', ref['strict'])
        R.save_results(); R.fault_check(since)
        R.log(f"tp1-r312c-multiq: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
        if r['strict'].get('exact') == '12/12':
            r['strict_run2'] = R.strict(srv.base, 'tp1-r312c-multiq-run2', ref['strict'])
            R.save_results(); R.fault_check(since)
            r['ladder'] = R.ladder_compare('tp1-r312c-multiq', R.ladder(srv.base, 'tp1-r312c-multiq', 2), ref['ladder'])
            R.save_results(); R.fault_check(since)
            R.CORPUS = AMD_CORPUS
            r['context'], _ = R.context(srv.base, 'tp1-r312c-multiq', R.TP2_LENGTHS, 32768, 2, ref['context'])
            R.CORPUS = LONG_CORPUS
            R.save_results(); R.fault_check(since)
            r['context_long'], _ = R.context(srv.base, 'tp1-r312c-multiq-long', LONG, 32768, 2, ref['long'])
            R.save_results(); R.fault_check(since)
            r['quality'], _ = R.quality(srv.base, 'tp1-r312c-multiq', 2, ref['quality'])
            R.save_results(); R.fault_check(since)
            r['history'] = R.history(srv.base, 'tp1-r312c-multiq')
            R.save_results(); R.fault_check(since)
            R.log(f"tp1-r312c-multiq: run2 {r['strict_run2'].get('tok_s_1_100')}, ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}, "
                  f"long {r['context_long'].get('passed')} {r['context_long'].get('by_length')}, quality {r['quality'].get('pass_all')}/{r['quality'].get('baseline_match_all')}, "
                  f"history {r['history'].get('divergent')}/{r['history'].get('logprob_divergent')}")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = os.environ.get('CAMPAIGN_UNIT', 'fp8-service-20260918-' + OUT.name.replace('fp8-', '').replace('-20260918', ''))
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
    R.log('=== lc-3 campaign complete ===')


if __name__ == '__main__':
    main()
