#!/usr/bin/env python3
"""FP8 27B two-card collectives campaign 2 (2026-09-17): the two-rank allreduce as one allgather plus a fixed-order add.

The overlay `b70-allgather-allreduce` (B70_ALLGATHER_ALLREDUCE=1) replaces `XpuCommunicator.all_reduce` for world size
2 with `all_gather_into_tensor` + `gathered[0] + gathered[1]`. The oneCCL environment is untouched (the pinned
SIMPLE_THRESHOLD ring switches stay; no peer-access kernels), so this is not a retry of the comm-1 threshold probe.

Stages (one stop of the running service, one start at the end):
  tp2-ag-mtp0   two cards, no MTP, overlay on: strict vs the R310 no-MTP reference (tells whether the sum is
                bit-identical to the ring allreduce), then ladder / context / quality, compared with the R310 no-MTP
                references when strict was 12/12, otherwise recorded as the overlay's own references
  tp2-ag-mtp5   two cards, depth 5 + INT4 draft shortlist + verifier rows, overlay on: strict twice (speed, two-run
                rule) vs the no-MTP strict, ladder r2 / context / quality vs the matching no-MTP references
  service       health, then the two-card package service on 18124 (no overlay), strict vs the R310 no-MTP reference

No retry. The fault latch (journal `coredump has been created`) halts the campaign; then the user decides.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-comm2-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', '/mnt/fast-ai/bench-results/service-postboot-20260917'))
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
REF = {'strict': REVIEW / 'tp2-mtp0-strict', 'ladder': REVIEW / 'tp2-mtp0-ladder.json',
       'context': REVIEW / 'tp2-mtp0-context/summary.json', 'quality': REVIEW / 'tp2-mtp0-quality.json'}
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
OVERLAY = ['--overlay', 'b70-allgather-allreduce', '--extra-env', 'B70_ALLGATHER_ALLREDUCE=1']
COMMON = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows']
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]


def gates(srv, name, refs, strict_runs=1):
    """Strict (n runs), ladder r2, context, quality against the given references; returns the result dict and the
    references this server produced (for the next stage)."""
    r = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    mine = {}
    if not srv.ready:
        return r, mine
    r['strict'] = R.strict(srv.base, name, refs['strict'])
    for i in range(2, strict_runs + 1):
        r[f'strict_run{i}'] = R.strict(srv.base, f'{name}-run{i}', refs['strict'])
    R.save_results(); R.fault_check(SINCE)
    mine['strict'] = OUT / f'{name}-strict'
    exact = r['strict'].get('exact') == '12/12' and r['strict'].get('rc') == 0
    R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
    ladder = R.ladder(srv.base, name, 2)
    r['ladder'] = R.ladder_compare(name, ladder, refs.get('ladder')) if refs.get('ladder') else {'verdict': 'reference recorded'}
    mine['ladder'] = ladder
    R.save_results(); R.fault_check(SINCE)
    r['context'], ctx = R.context(srv.base, name, R.TP2_LENGTHS, R.TP2_MML, 2, refs.get('context'))
    mine['context'] = ctx
    R.save_results(); R.fault_check(SINCE)
    r['quality'], q = R.quality(srv.base, name, 2, refs.get('quality'))
    mine['quality'] = q
    R.save_results(); R.fault_check(SINCE)
    r['all_exact'] = (exact and r['ladder'].get('verdict') in ('exact', 'reference recorded') and r['context'].get('passed') is True
                      and r['quality'].get('pass_all') is True and r['quality'].get('baseline_match_all') in (True, None))
    R.log(f"{name}: ladder {r['ladder'].get('verdict')}, context passed={r['context'].get('passed')}, "
          f"quality pass={r['quality'].get('pass_all')} baseline_match={r['quality'].get('baseline_match_all')}")
    return r, mine


def main():
    global SINCE
    OUT.mkdir(parents=True, exist_ok=False)
    SINCE = R.now()
    R.log(f'comm-2 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = SINCE
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(SINCE)

    # Stage 1: the no-MTP reference under the overlay.
    srv = R.Research('tp2-ag-mtp0', 18192, COMMON + OVERLAY)
    if srv.ready:
        # Strict first: if bit-identical to the ring allreduce, the other gates compare with the R310 references too.
        r = results['tp2-ag-mtp0'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        r['strict'] = R.strict(srv.base, 'tp2-ag-mtp0', REF['strict'])
        R.save_results(); R.fault_check(SINCE)
        identical = r['strict'].get('exact') == '12/12' and r['strict'].get('rc') == 0
        R.log(f"tp2-ag-mtp0: strict vs ring-allreduce reference {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
        refs = dict(REF) if identical else {'strict': REF['strict']}
        ladder = R.ladder(srv.base, 'tp2-ag-mtp0', 2)
        r['ladder'] = R.ladder_compare('tp2-ag-mtp0', ladder, refs.get('ladder')) if refs.get('ladder') else {'verdict': 'reference recorded'}
        R.save_results(); R.fault_check(SINCE)
        r['context'], ctx = R.context(srv.base, 'tp2-ag-mtp0', R.TP2_LENGTHS, R.TP2_MML, 2, refs.get('context'))
        R.save_results(); R.fault_check(SINCE)
        r['quality'], q = R.quality(srv.base, 'tp2-ag-mtp0', 2, refs.get('quality'))
        R.save_results(); R.fault_check(SINCE)
        r['identical_to_ring_allreduce'] = identical
        r['all_exact'] = (r['ladder'].get('verdict') in ('exact', 'reference recorded') and r['context'].get('passed') is True
                          and r['quality'].get('pass_all') is True and r['quality'].get('baseline_match_all') in (True, None))
        R.log(f"tp2-ag-mtp0: ladder {r['ladder'].get('verdict')}, context passed={r['context'].get('passed')}, quality pass={r['quality'].get('pass_all')}")
        mtp0_refs = {'strict': OUT / 'tp2-ag-mtp0-strict', 'ladder': ladder, 'context': ctx, 'quality': q}
    else:
        results['tp2-ag-mtp0'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        mtp0_refs = None
    results['tp2-ag-mtp0']['stop'] = srv.stop()
    R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()

    # Stage 2: the depth-5 candidate under the overlay, gated against the overlay's own no-MTP outputs.
    if mtp0_refs and mtp0_refs['strict'].exists():
        srv = R.Research('tp2-ag-mtp5', 18193, COMMON + MTP5 + OVERLAY)
        results['tp2-ag-mtp5'], _ = gates(srv, 'tp2-ag-mtp5', mtp0_refs, strict_runs=2)
        results['tp2-ag-mtp5']['stop'] = srv.stop()
        R.save_results(); R.fault_check(SINCE); R.wait_gpus_free()
    else:
        R.log('no overlay no-MTP reference; skipping the depth-5 candidate')

    # Stage 3: the service back, unchanged.
    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917-comm2'
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
    R.log('=== comm-2 campaign complete ===')


if __name__ == '__main__':
    main()
