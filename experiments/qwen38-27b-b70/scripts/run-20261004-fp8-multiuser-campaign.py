#!/usr/bin/env python3
"""FP8 27B multi-user campaign 1 (2026-10-04): how many users at once still get exactly their solo answers, and how fast.

Preregistration: notes/2026-10-04-fp8-multiuser-prereg.md.

Stages (no resident server before or after; each server started once, stopped gracefully, no retry):
  tp2-mtp0-s8   two cards, no speculation, the server accepts 8 sequences: sequential oracle, then 2, 4 and 8 users
                at once, twice each
  tp2-mtp5-s4   two cards, the shipped depth-5 recipe, the server accepts 4 sequences: oracle, then 2 and 4 users
  tp1-mtp0-s8   one card, no speculation, 8 sequences (only with MU_TP1=1)

Every concurrent answer is compared token for token with the same request run alone on the same server
(scripts/bench-openai-concurrency-oracle.py). Speed is the sum of generated tokens over the batch's wall time.
A GPU fault line halts the campaign.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-multiuser-20261004'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path('/nonexistent/no-resident-service')
SHIPPED = ['--overlay', 'b70-allgather-allreduce', '--extra-env', 'B70_ALLGATHER_ALLREDUCE=1']
TP2 = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows']
MTP5 = ['--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST]


def oracle(base, name, levels):
    out = OUT / f'{name}-concurrency.json'
    R.sh([sys.executable, R.LADDER, '--base-url', base, '--model', R.MODEL_NAME, '--api-mode', 'completions',
          '--suite', R.LADDER_SUITE, '--concurrency', levels, '--repeats', '2', '--max-tokens', '128',
          '--seed', '42', '--timeout', '1800', '--return-token-ids', '--out', out], f'{name}-concurrency', 5400)
    if not out.exists():
        return {'error': 'no output'}
    data = json.loads(out.read_text())
    rows = [{'users': b['concurrency'], 'repeat': b['repeat'], 'exact': f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
             'aggregate_tok_s': round(b['aggregate_tok_s_wall'], 2), 'per_user_tok_s_median': round(b['per_request_tok_s_wall_median'], 2),
             'cache_zero': b['cached_tokens_all_zero']} for b in data['batches']]
    for row in rows:
        R.log(f"{name}: {row['users']} user(s), repeat {row['repeat']}: exact {row['exact']}, "
              f"{row['aggregate_tok_s']} tok/s together, {row['per_user_tok_s_median']} per user")
    return {'classification': data.get('classification'), 'levels': rows}


def stage(results, since, name, port, args, levels):
    srv = R.Research(name, port, args)
    r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        r['concurrency'] = oracle(srv.base, name, levels)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'multi-user campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = since
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)
    stage(results, since, 'tp2-mtp0-s8', 18196, TP2 + SHIPPED + ['--seqs', '8'], '2,4,8')
    stage(results, since, 'tp2-mtp5-s4', 18197, TP2 + MTP5 + SHIPPED + ['--seqs', '4'], '2,4')
    if os.environ.get('MU_TP1') == '1':
        stage(results, since, 'tp1-mtp0-s8', 18198, ['--tp', '1', '--gpu', '0', '--mem', '0.965', '--max-model-len', '20480',
                                                   '--batched', '4096', '--cpu-embed', '--fa-verify-rows', '--seqs', '8'], '2,4,8')
    results['finished'] = R.now()
    R.save_results()
    R.log('=== multi-user campaign complete (cards left empty) ===')


if __name__ == '__main__':
    main()
