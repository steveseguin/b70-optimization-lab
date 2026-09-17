#!/usr/bin/env python3
"""FP8 27B night campaign 3 (package profile replays, broad-text shortlist, two-card arm B), 2026-09-17 (after the second GPU fault; user chose to try the GPUs without a reset).

Stages, in this order because the two faults both hit a two-card start *after* long one-card work:
  service-a      two-card depth-5 package service from idle (fault arm A): start, strict parity vs the same-image
                 no-MTP reference, then one owned stop. A fault here ends the campaign.
  tp1-32k-m985   one card, depth 5 + shortlist, 32,768 context, 2,048-token chunk, memory 0.985 (0.3 GiB more than the
                 shipped 0.975): KV budget recorded; if it starts, strict, 64-prompt oracle + queued pass, 2K/8K/16K
                 screen vs the follow-up no-MTP reference
  tp1-graph      one card, shipped 24K settings plus XPU graph capture (VLLM_XPU_ENABLE_XPU_GRAPH=1) with
                 --enable-prompt-embeds so the host-embedding lookup runs outside the captured graph: recorded as a
                 gated probe (strict, oracle, screen); any divergence disqualifies it
  service-b      health, then the two-card service again (fault arm B: after one-card work), parity, left running

Rules: no restart or retry; a fault latches the campaign (evidence preserved, nothing restored); speed recorded, never
gated; power and driver state untouched.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-night3-20260917'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
REVIEW = Path('/mnt/fast-ai/bench-results/fp8-review-20260916')
FOLLOWUP = Path('/mnt/fast-ai/bench-results/fp8-followup-20260917')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
TP1_LADDER = Path('/mnt/fast-ai/bench-results/fp8-review-20260916-attempt1/tp1-mtp0-ladder.json')
TP1_CTX = FOLLOWUP / 'tp1-mtp0-long-context/summary.json'
TP2_STRICT = REVIEW / 'tp2-mtp0-strict'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LONG = '2048,8192,16384'
ONE_CARD = ['--tp', '1', '--gpu', '0', '--cpu-embed', '--fa-verify-rows', '--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]


def memory_lines(out):
    log = out / 'server.log'
    if not log.exists():
        return []
    return [line.strip()[-200:] for line in log.read_text(errors='replace').splitlines()
            if any(k in line for k in ('KV cache', 'Actual usage', 'larger than', 'XPU Graph', 'cudagraph', 'Capturing'))][-8:]


def service(name, unit):
    state_dir = OUT / name
    argv = ['systemd-run', '--user', '--unit', unit, '--working-directory', str(ROOT), '--collect',
            sys.executable, str(PKG_TP2), 'start', '--model-dir', str(R.MODEL), '--state-dir', str(state_dir), '--port', '18124']
    R.wait_port_free(18124)
    (OUT / f'{name}.command.json').write_text(json.dumps({'argv': argv, 'started': R.now()}) + '\n')
    subprocess.run(argv, check=True)
    deadline = time.monotonic() + 2400
    state = {}
    while time.monotonic() < deadline:
        if (state_dir / 'state.json').exists():
            state = json.loads((state_dir / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        time.sleep(10)
    result = {'status': state.get('status'), 'error': state.get('error'), 'unit': unit, 'state_dir': str(state_dir)}
    R.log(f'{name}: {state.get("status")} {state.get("error") or ""}')
    if state.get('status') == 'ready':
        result['strict'] = R.strict('http://127.0.0.1:18124', name, TP2_STRICT)
    return result, state_dir


def stop_service(state_dir):
    result = R.helper.run([sys.executable, str(PKG_TP2), 'stop', '--state-dir', str(state_dir)], check=False, timeout=90)
    R.log(f'stop {state_dir.name}: rc={result.returncode} {result.stderr.strip()[:120]}')
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        state = json.loads((state_dir / 'state.json').read_text())
        if state.get('status') in ('stopped', 'failed'):
            return state.get('status')
        time.sleep(5)
    return 'stop timeout'


SHORTLIST_V3 = ROOT / 'experiments/qwen38-27b-b70/docker/draft-shortlists/shortlist-v3-top65536.txt'


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'night-3 campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    if not SHORTLIST_V3.exists():
        raise RuntimeError(f'missing {SHORTLIST_V3}')
    results = R.RESULTS
    results['started'] = since
    R.save_results()
    R.SERVICE_STATE = Path(os.environ.get('SERVICE_STATE', '/mnt/fast-ai/bench-results/fp8-night2-20260917/service-c'))
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        R.log('preflight health probe failed; halting before any server')
        raise SystemExit(4)
    R.fault_check(since)

    # ---- the shipped one-card launcher, new profiles
    for name, profile, port, mml in (('tp1-pkg-max-context', 'max-context', 18135, 30720), ('tp1-pkg-no-quantization-20k', 'no-quantization', 18136, 20480)):
        pkg = R.Package(name, profile, port)
        r = results[name] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if pkg.ready:
            r['strict'] = R.strict(pkg.base, name, R.TP1_MTP0_STRICT)
            r['ladder'] = R.ladder_compare(name, R.ladder(pkg.base, name, 1), TP1_LADDER)
            r['context'], _ = R.context(pkg.base, name, LONG, mml, 2, TP1_CTX)
            r['status_rc'] = pkg.status()
        r['stop'] = pkg.stop()
        r['memory_lines'] = memory_lines(pkg.out)
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- one-card probes lost to the night-2 false alarm: 32K at depth 4, and graph capture on the 24K settings
    base = ['--tp', '1', '--gpu', '0', '--cpu-embed', '--fa-verify-rows', '--draft-int4', '--shortlist', R.SHORTLIST]
    for name, port, extra in (('tp1-32k-d4-m983', 18173, ['--mem', '0.983', '--max-model-len', '32768', '--batched', '2048', '--mtp', '4']),
                              ('tp1-graph-24k', 18174, ['--mem', '0.975', '--max-model-len', '24576', '--batched', '2048', '--mtp', '5',
                                                        '--env', 'VLLM_XPU_ENABLE_XPU_GRAPH=1', '--extra-env', 'B70_CPU_EMBED_ALLOW_GRAPH=1',
                                                        '--serve-arg=--enable-prompt-embeds'])):
        srv = R.Research(name, port, base + extra)
        r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            r['strict'] = R.strict(srv.base, name, R.TP1_MTP0_STRICT)
            r['ladder'] = R.ladder_compare(name, R.ladder(srv.base, name, 1), TP1_LADDER)
            r['context'], _ = R.context(srv.base, name, LONG, int(extra[extra.index('--max-model-len') + 1]), 2, TP1_CTX)
        r['stop'] = srv.stop()
        r['memory_lines'] = memory_lines(srv.out)
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    # ---- two cards: broad-text shortlist v3 vs the shipped list, same session
    tp2 = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows', '--mtp', '5', '--draft-int4']
    for name, port, extra in (('tp2-mtp5-shortlist-v3', 18180, ['--mount-file', f'{SHORTLIST_V3}:/opt/draft-shortlists/shortlist-v3-top65536.txt',
                                                               '--shortlist', '/opt/draft-shortlists/shortlist-v3-top65536.txt']),
                              ('tp2-mtp5-shortlist-old', 18181, ['--shortlist', R.SHORTLIST])):
        srv = R.Research(name, port, tp2 + extra)
        r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            r['strict'] = R.strict(srv.base, name, TP2_STRICT)
            if 'v3' in name:
                r['ladder'] = R.ladder_compare(name, R.ladder(srv.base, name, 1), REVIEW / 'tp2-mtp0-ladder.json')
                r['context'], _ = R.context(srv.base, name, R.TP2_LENGTHS, R.TP2_MML, 2, REVIEW / 'tp2-mtp0-context/summary.json')
        r['stop'] = srv.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('health probe failed before the service start; service left down')
        raise SystemExit(5)
    results['service-d'], _ = service('service-d', 'fp8-service-20260917f')
    R.save_results(); R.fault_check(since)
    results['finished'] = R.now()
    R.save_results()
    R.log('=== night-3 campaign complete ===')


if __name__ == '__main__':
    main()
