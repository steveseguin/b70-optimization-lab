#!/usr/bin/env python3
"""FP8 27B follow-up campaign, 2026-09-17: the pieces the review campaign left open, then the two-card package
acceptance session, then the new service. One unattended runner; one stop of the running service; one final start.

Stages:
  tp1-mtp0-long           one card, R310, no MTP, 20,480 context: 2K/8K/16K context reference (two repeats)
  tp1-pkg-no-quantization the shipped one-card `no-quantization` profile: 64-prompt oracle + queued pass vs the
                          review campaign's one-card no-MTP ladder, strict suite vs the R310 no-MTP strict run, clean stop
  tp1-ctx-*               one-card context-length probes at depth 5 (draft shortlist, host embedding, verifier rows):
                          24,576 context at 4,096 and 2,048 batched tokens, 32,768 at 2,048. A probe that reaches ready
                          runs the strict suite, the 64-prompt oracle and the 2K/8K/16K screen vs tp1-mtp0-long.
  tp2-mtp6                two cards, MTP depth 6 + shortlist: strict, oracle, context, quality vs the review campaign's
                          two-card no-MTP references
  acceptance              run-fp8-tp2-acceptance-session.py at the pushed commit named in <out>/COMMIT (waits for it)
  service                 health probe, then the new two-card package service on 18124 in its own unit, strict parity
                          vs the same-image no-MTP reference

Reuses the review runner's building blocks (run-20260916-fp8-review-campaign.py). Same rules: no restart or retry,
fault latch halts everything, speed recorded never gated, nothing touches power or driver state.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-followup-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
review.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', str(REVIEW / 'service-restored-6')))
R = review
TP1_LADDER = Path('/mnt/fast-ai/bench-results/fp8-review-20260916-attempt1/tp1-mtp0-ladder.json')
TP2_LADDER = REVIEW / 'tp2-mtp0-ladder.json'
TP2_CTX = REVIEW / 'tp2-mtp0-context/summary.json'
TP2_QUALITY = REVIEW / 'tp2-mtp0-quality.json'
TP2_STRICT = REVIEW / 'tp2-mtp0-strict'
ACCEPTANCE = ROOT / 'experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'follow-up campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    for path in (TP1_LADDER, TP2_LADDER, TP2_CTX, TP2_QUALITY, TP2_STRICT, ACCEPTANCE, PKG_TP2):
        if not path.exists():
            raise RuntimeError(f'missing {path}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    # The running service was started by the September 14 launcher (state schema v1); stop it with that launcher.
    R.PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve-r304-depth1.py'
    R.stop_service()
    R.PKG_TP2 = PKG_TP2
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        R.log('preflight health probe failed; halting before any server')
        raise SystemExit(4)
    R.fault_check(since)

    # ---- one card, no MTP, long-length context reference
    ref = R.tp1_research('tp1-mtp0-long', 18150, ['--mtp', '0'])
    tp1_ctx = None
    results['tp1-mtp0-long'] = {'server': ref.state.get('status')}
    if ref.ready:
        results['tp1-mtp0-long']['context'], tp1_ctx = R.context(ref.base, 'tp1-mtp0-long', LONG, 20480, 2)
    results['tp1-mtp0-long']['stop'] = ref.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- the shipped one-card no-quantization profile
    pkg = R.Package('tp1-pkg-no-quantization', 'no-quantization', 18131)
    r = results['tp1-pkg-no-quantization'] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if pkg.ready:
        r['ladder'] = R.ladder_compare('tp1-pkg-no-quantization', R.ladder(pkg.base, 'tp1-pkg-no-quantization', 1), TP1_LADDER)
        r['strict'] = R.strict(pkg.base, 'tp1-pkg-no-quantization', R.TP1_MTP0_STRICT)
        r['status_rc'] = pkg.status()
    r['stop'] = pkg.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- one-card context-length probes at depth 5
    probes = [('tp1-ctx-24k-b4096', 24576, 4096), ('tp1-ctx-24k-b2048', 24576, 2048), ('tp1-ctx-32k-b2048', 32768, 2048)]
    for index, (name, mml, batched) in enumerate(probes):
        srv = R.Research(name, 18152 + index, ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--max-model-len', str(mml),
                                                '--batched', str(batched), '--cpu-embed', '--fa-verify-rows', '--mtp', '5',
                                                '--draft-int4', '--shortlist', R.SHORTLIST])
        r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')},
                             'memory_log': [line for line in json.loads((srv.out / 'state.json').read_text()).get('memory_log', [])
                                            if any(k in line for k in ('KV cache', 'Actual usage', 'ValueError', 'larger than', 'Model loading'))][-8:]
                             if (srv.out / 'state.json').exists() else []}
        if srv.ready:
            r['strict'] = R.strict(srv.base, name, R.TP1_MTP0_STRICT)
            r['ladder'] = R.ladder_compare(name, R.ladder(srv.base, name, 1), TP1_LADDER)
            r['context'], _ = R.context(srv.base, name, LONG, mml, 2, tp1_ctx)
        r['stop'] = srv.stop()
        r['memory_log'] = [line for line in json.loads((srv.out / 'state.json').read_text()).get('memory_log', [])
                           if any(k in line for k in ('KV cache', 'Actual usage', 'ValueError', 'larger than', 'Model loading'))][-8:]
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- two cards, depth 6
    srv = R.tp2_research('tp2-mtp6', 18160, ['--mtp', '6', '--draft-int4', '--shortlist', R.SHORTLIST])
    r = results['tp2-mtp6'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        r['strict'] = R.strict(srv.base, 'tp2-mtp6', TP2_STRICT)
        r['ladder'] = R.ladder_compare('tp2-mtp6', R.ladder(srv.base, 'tp2-mtp6', 2), TP2_LADDER)
        r['context'], _ = R.context(srv.base, 'tp2-mtp6', R.TP2_LENGTHS, R.TP2_MML, 2, TP2_CTX)
        r['quality'], _ = R.quality(srv.base, 'tp2-mtp6', 1, TP2_QUALITY)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- acceptance session of the pushed two-card package
    commit_file = OUT / 'COMMIT'
    deadline = time.monotonic() + 3 * 3600
    while not commit_file.exists() and time.monotonic() < deadline:
        time.sleep(30)
    if not commit_file.exists():
        R.log('no COMMIT file within three hours; skipping the acceptance session and the service start')
        raise SystemExit(6)
    commit = commit_file.read_text().strip()
    R.log(f'acceptance session at commit {commit}')
    rc = R.sh([sys.executable, ACCEPTANCE, '--commit', commit, '--out', OUT / 'acceptance'], 'acceptance', 7200)
    results['acceptance'] = {'commit': commit, 'rc': rc}
    if (OUT / 'acceptance/session-rcs.json').exists():
        results['acceptance']['rcs'] = json.loads((OUT / 'acceptance/session-rcs.json').read_text())
    R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- the new service, in its own unit so it outlives this runner
    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('health probe failed before the service start; service left down')
        raise SystemExit(5)
    state_dir = OUT / 'service'
    unit = 'fp8-service-20260917'
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
    R.log('=== follow-up campaign complete ===')


if __name__ == '__main__':
    main()
