#!/usr/bin/env python3
"""FP8 27B two-card campaign 3 (2026-09-17 evening): the replicated drafter and the single-checkpoint state on two cards.

All servers carry the shipped allgather-allreduce overlay. Stages (one stop of the service, one start at the end):
  tp2-ag-mtp0-b896   R310, no MTP, `--block-size 896`: strict vs the comm-2 no-MTP reference (informational), ladder r2,
                     2K/8K/16K, chat quality: the no-MTP references at the attention block the checkpoint page implies
  tp2-rd-mtp5        R310, depth 5 + INT4 shortlist + verifier rows + replicated drafter: strict twice vs the comm-2
                     no-MTP reference, ladder r2, context, quality vs the comm-2 references
  tp2-ck-mtp5        R311b, depth 5 + single-checkpoint state: strict twice vs the 896 reference, ladder, context,
                     quality vs the 896 references
  tp2-all-mtp5       R311b, both overlays (only if both passed): the same gates vs the 896 references
  service            the two-card package service on 18124, strict vs the comm-2 no-MTP reference
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

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-comm3-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])
R311B = os.environ.get('R311_IMAGE', 'sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7')
COMM2 = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917')
REF832 = {'strict': COMM2 / 'tp2-ag-mtp0-strict', 'ladder': COMM2 / 'tp2-ag-mtp0-ladder.json',
          'context': COMM2 / 'tp2-ag-mtp0-context/summary.json', 'quality': COMM2 / 'tp2-ag-mtp0-quality.json'}
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
AG = ['--overlay', 'b70-allgather-allreduce', '--extra-env', 'B70_ALLGATHER_ALLREDUCE=1']
RD = ['--overlay', 'b70-replicated-drafter', '--extra-env', 'B70_REPLICATED_DRAFTER=1']
CK = ['--overlay', 'b70-gdn-checkpoint', '--extra-env', 'B70_GDN_CHECKPOINT=1', '--image', R311B]
COMMON = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows']
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]


def gates(srv, name, refs, strict_runs=2):
    r = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}, 'all_exact': False}
    if not srv.ready:
        return r
    r['strict'] = R.strict(srv.base, name, refs['strict'])
    R.save_results(); R.fault_check(SINCE)
    exact = r['strict'].get('exact') == '12/12' and r['strict'].get('rc') == 0
    R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
    if not exact:
        return r
    for i in range(2, strict_runs + 1):
        r[f'strict_run{i}'] = R.strict(srv.base, f'{name}-run{i}', refs['strict'])
        R.save_results(); R.fault_check(SINCE)
    r['ladder'] = R.ladder_compare(name, R.ladder(srv.base, name, 2), refs['ladder'])
    R.save_results(); R.fault_check(SINCE)
    r['context'], _ = R.context(srv.base, name, R.TP2_LENGTHS, R.TP2_MML, 2, refs['context'])
    R.save_results(); R.fault_check(SINCE)
    r['quality'], _ = R.quality(srv.base, name, 2, refs['quality'])
    R.save_results(); R.fault_check(SINCE)
    r['all_exact'] = (r['ladder'].get('verdict') == 'exact' and r['context'].get('passed') is True
                      and r['quality'].get('pass_all') is True and r['quality'].get('baseline_match_all') is True)
    R.log(f"{name}: run2 {r.get('strict_run2', {}).get('tok_s_1_100')} tok/s, ladder {r['ladder'].get('verdict')}, context {r['context'].get('passed')}, "
          f"quality {r['quality'].get('pass_all')}/{r['quality'].get('baseline_match_all')} -> all_exact={r['all_exact']}")
    return r


def main():
    global SINCE
    OUT.mkdir(parents=True, exist_ok=False)
    SINCE = R.now()
    R.log(f'comm-3 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = SINCE
    for path in REF832.values():
        if not path.exists():
            raise SystemExit(f'missing reference: {path}')
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(SINCE)

    # 1. no-MTP references at block 896
    srv = R.Research('tp2-ag-mtp0-b896', 18203, COMMON + AG + ['--serve-arg=--block-size', '--serve-arg=896'])
    r = results['tp2-ag-mtp0-b896'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    ref896 = None
    if srv.ready:
        r['strict_vs_832'] = R.strict(srv.base, 'tp2-ag-mtp0-b896', REF832['strict'])
        R.save_results(); R.fault_check(SINCE)
        R.log(f"tp2-ag-mtp0-b896: strict vs the 832 reference {r['strict_vs_832'].get('exact')} at {r['strict_vs_832'].get('tok_s_1_100')} tok/s")
        ladder = R.ladder(srv.base, 'tp2-ag-mtp0-b896', 2)
        R.save_results(); R.fault_check(SINCE)
        r['context'], ctx = R.context(srv.base, 'tp2-ag-mtp0-b896', R.TP2_LENGTHS, R.TP2_MML, 2)
        R.save_results(); R.fault_check(SINCE)
        r['quality'], q = R.quality(srv.base, 'tp2-ag-mtp0-b896', 2)
        R.save_results(); R.fault_check(SINCE)
        if r['strict_vs_832'].get('rc') == 0 and ladder and ctx and q:
            ref896 = {'strict': OUT / 'tp2-ag-mtp0-b896-strict', 'ladder': ladder, 'context': ctx, 'quality': q}
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # 2. replicated drafter (R310)
    srv = R.Research('tp2-rd-mtp5', 18204, COMMON + MTP5 + AG + RD)
    results['tp2-rd-mtp5'] = gates(srv, 'tp2-rd-mtp5', REF832)
    results['tp2-rd-mtp5']['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()
    rd_ok = results['tp2-rd-mtp5']['all_exact']

    # 3. single-checkpoint state (R311b)
    ck_ok = False
    if ref896:
        srv = R.Research('tp2-ck-mtp5', 18205, COMMON + MTP5 + AG + CK)
        results['tp2-ck-mtp5'] = gates(srv, 'tp2-ck-mtp5', ref896)
        results['tp2-ck-mtp5']['stop'] = srv.stop()
        R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()
        ck_ok = results['tp2-ck-mtp5']['all_exact']
    else:
        R.log('no 896 references; skipping the checkpoint stages')

    # 4. both
    if rd_ok and ck_ok:
        srv = R.Research('tp2-all-mtp5', 18206, COMMON + MTP5 + AG + RD + CK)
        results['tp2-all-mtp5'] = gates(srv, 'tp2-all-mtp5', ref896)
        results['tp2-all-mtp5']['stop'] = srv.stop()
        R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()
    else:
        R.log(f'combined stage skipped (replicated drafter exact={rd_ok}, checkpoint exact={ck_ok})')

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-comm3'
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
        results['service']['strict'] = R.strict('http://127.0.0.1:18124', 'service', REF832['strict'])
    R.save_results(); R.fault_check(SINCE)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== comm-3 campaign complete ===')


if __name__ == '__main__':
    main()
