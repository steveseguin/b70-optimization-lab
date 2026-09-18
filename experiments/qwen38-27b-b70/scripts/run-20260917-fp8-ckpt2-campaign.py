#!/usr/bin/env python3
"""FP8 27B one-card single-checkpoint campaign 2 (2026-09-17): the attention block size question.

ckpt-1b: the checkpoint server was 10/12 vs the R310 no-MTP reference (divergences at tokens 341 and 127 of two
prompts) at 52.9 tok/s. Its Mamba page grew by the stash, so vLLM raised the attention block from 832 to 896 tokens;
the reference ran at 832. If the attention kernels' accumulation depends on the block boundaries, that alone explains
a rare late divergence. This campaign settles it with same-block-size references:

  tp1-mtp0-b896    stock R310, no MTP, `--block-size 896`: strict (vs the 832 reference, informational), ladder r2,
                   2K/8K/16K, chat quality: the references at 896
  tp1-stock-b896   stock R310, depth 5 (shipped recipe), `--block-size 896`: strict vs the 832 reference and vs
                   tp1-mtp0-b896 (the checkpoint kernel is not involved: this isolates the block size)
  tp1-ckpt-mtp5    R311 + b70-gdn-checkpoint (block 896 by construction): strict vs tp1-mtp0-b896, then ladder,
                   context, quality vs the 896 references; strict twice for speed
  tp1-ckpt-32k     if all exact: 32,768 context at 0.975 with the 30,720 probe
  service          the two-card package service back on 18124, strict vs the two-card no-MTP reference

R311_IMAGE names the checkpoint image. One service stop, one start. No retry; fault latch as before.
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

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-ckpt2-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
R311 = os.environ['R311_IMAGE']
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
TP2_STRICT = REVIEW / 'tp2-mtp0-strict'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384'
B896 = ['--serve-arg=--block-size', '--serve-arg=896']
COMMON = ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--batched', '2048', '--cpu-embed', '--fa-verify-rows']
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]
CKPT = ['--overlay', 'b70-gdn-checkpoint', '--extra-env', 'B70_GDN_CHECKPOINT=1', '--image', R311]


def kv_lines(name):
    log = OUT / f'{name}-owner.log'
    if not log.exists():
        return []
    keep = re.compile(r'KV cache|Maximum concurrency|b70_gdn_checkpoint: stash|attention block size|Padding mamba', re.I)
    return [line.strip()[:240] for line in log.read_text(errors='replace').splitlines() if keep.search(line)][:24]


def server(name, port, args):
    srv = R.Research(name, port, args)
    return srv, {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}, 'kv_lines': kv_lines(name)}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'ckpt-2 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}; image {R311}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    # 1. no-MTP references at block 896
    srv, r = server('tp1-mtp0-b896', 18196, COMMON + B896 + ['--max-model-len', '24576'])
    results['tp1-mtp0-b896'] = r
    ref = {}
    if srv.ready:
        r['strict_vs_832'] = R.strict(srv.base, 'tp1-mtp0-b896', R.TP1_MTP0_STRICT)
        R.save_results(); R.fault_check(since)
        R.log(f"tp1-mtp0-b896: strict vs the 832 reference {r['strict_vs_832'].get('exact')} at {r['strict_vs_832'].get('tok_s_1_100')} tok/s")
        ref['strict'] = OUT / 'tp1-mtp0-b896-strict'
        ref['ladder'] = R.ladder(srv.base, 'tp1-mtp0-b896', 2)
        R.save_results(); R.fault_check(since)
        r['context'], ref['context'] = R.context(srv.base, 'tp1-mtp0-b896', LONG, 24576, 2)
        R.save_results(); R.fault_check(since)
        r['quality'], ref['quality'] = R.quality(srv.base, 'tp1-mtp0-b896', 2)
        R.save_results(); R.fault_check(since)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()
    if not ref.get('strict') or not ref['strict'].exists():
        raise SystemExit('no 896 reference')

    # 2. stock depth 5 at block 896: isolates the block size
    srv, r = server('tp1-stock-b896', 18197, COMMON + MTP5 + B896 + ['--max-model-len', '24576'])
    results['tp1-stock-b896'] = r
    if srv.ready:
        r['strict_vs_832'] = R.strict(srv.base, 'tp1-stock-b896', R.TP1_MTP0_STRICT)
        r['strict_vs_896'] = {'reference': str(ref['strict'])}
        cmp = OUT / 'tp1-stock-b896-strict-vs-896.json'
        R.sh([sys.executable, R.COMPARE_STRICT, OUT / 'tp1-stock-b896-strict', ref['strict'], '--output', cmp], 'tp1-stock-b896-strict-compare-896', 300)
        if cmp.exists():
            c = json.loads(cmp.read_text())['comparison']
            r['strict_vs_896']['exact'] = f"{c['exact_prompts']}/{c['total_prompts']}"
            r['strict_vs_896']['divergent'] = c.get('divergent_prompts')
        R.log(f"tp1-stock-b896: strict vs 832 {r['strict_vs_832'].get('exact')}, vs 896 {r['strict_vs_896'].get('exact')}, {r['strict_vs_832'].get('tok_s_1_100')} tok/s")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # 3. the checkpoint kernel vs the 896 references
    all_exact = False
    srv, r = server('tp1-ckpt-mtp5', 18198, COMMON + MTP5 + CKPT + ['--max-model-len', '24576'])
    results['tp1-ckpt-mtp5'] = r
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp1-ckpt-mtp5', ref['strict'])
        R.save_results(); R.fault_check(since)
        exact = r['strict'].get('exact') == '12/12' and r['strict'].get('rc') == 0
        R.log(f"tp1-ckpt-mtp5: strict vs 896 reference {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
        if exact:
            r['strict_run2'] = R.strict(srv.base, 'tp1-ckpt-mtp5-run2', ref['strict'])
            R.save_results(); R.fault_check(since)
            r['ladder'] = R.ladder_compare('tp1-ckpt-mtp5', R.ladder(srv.base, 'tp1-ckpt-mtp5', 2), ref['ladder'])
            R.save_results(); R.fault_check(since)
            r['context'], _ = R.context(srv.base, 'tp1-ckpt-mtp5', LONG, 24576, 2, ref['context'])
            R.save_results(); R.fault_check(since)
            r['quality'], _ = R.quality(srv.base, 'tp1-ckpt-mtp5', 2, ref['quality'])
            R.save_results(); R.fault_check(since)
            all_exact = (r['ladder'].get('verdict') == 'exact' and r['context'].get('passed') is True
                         and r['quality'].get('pass_all') is True and r['quality'].get('baseline_match_all') is True)
            R.log(f"tp1-ckpt-mtp5: ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}, quality {r['quality'].get('pass_all')}/{r['quality'].get('baseline_match_all')} -> all_exact={all_exact}")
        r['all_exact'] = all_exact
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    if all_exact:
        srv, r = server('tp1-ckpt-32k', 18199, COMMON + MTP5 + CKPT + ['--max-model-len', '32768'])
        results['tp1-ckpt-32k'] = r
        if srv.ready:
            r['strict'] = R.strict(srv.base, 'tp1-ckpt-32k', ref['strict'])
            R.save_results(); R.fault_check(since)
            r['context'], _ = R.context(srv.base, 'tp1-ckpt-32k', LONG, 32768, 2, ref['context'])
            R.save_results(); R.fault_check(since)
            r['context_30720'], _ = R.context(srv.base, 'tp1-ckpt-32k-30720', '30720', 32768, 2)
            R.save_results(); R.fault_check(since)
            R.log(f"tp1-ckpt-32k: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s, context {r['context'].get('passed')}, 30720 probe {r['context_30720'].get('passed')}")
        r['stop'] = srv.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()
    else:
        R.log('checkpoint gates not exact; skipping the 32K stage')

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-ckpt2'
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
    R.log('=== ckpt-2 campaign complete ===')


if __name__ == '__main__':
    main()
