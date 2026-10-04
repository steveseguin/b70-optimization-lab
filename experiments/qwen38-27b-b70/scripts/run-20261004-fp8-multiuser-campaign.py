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


REF_LADDER = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-ladder.json')  # frozen single-user no-MTP answers


def saturated(base, name):
    """All 64 prompts sent at once to a server that runs N of them together: every answer against (a) the same
    server's one-at-a-time answers and (b) the frozen single-user no-speculation reference. Two passes."""
    ladder = R.ladder(base, name, 2)
    if not ladder:
        return {'error': 'no ladder output'}
    data = json.loads(Path(ladder).read_text())
    out = {'vs_reference': R.ladder_compare(name, ladder, REF_LADDER),
           'passes': [{'repeat': b['repeat'], 'answers': b['request_count'],
                       'exact_vs_own_solo': f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
                       'aggregate_tok_s': round(b['aggregate_tok_s_wall'], 2), 'cache_zero': b['cached_tokens_all_zero']}
                      for b in data['batches']]}
    for row in out['passes']:
        R.log(f"{name}: pass {row['repeat']}: {row['exact_vs_own_solo']} equal to solo, {row['aggregate_tok_s']} tok/s together")
    R.log(f"{name}: vs the frozen single-user reference: {out['vs_reference'].get('verdict')} {out['vs_reference'].get('sections')}")
    return out


def stage(results, since, name, port, args, levels):
    srv = R.Research(name, port, args)
    r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    if srv.ready:
        if levels == 'saturated':
            r['saturated'] = saturated(srv.base, name)
        else:
            r['concurrency'] = oracle(srv.base, name, levels)
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()


INVARIANT = []
for _key in ('VLLM_XPU_FP8_PACKED_SERIAL_EXACT', 'VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT',
             'VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT', 'VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT',
             'VLLM_XPU_FA_SERIAL_SPEC_DECODE', 'VLLM_XPU_LM_HEAD_BATCH_INVARIANT',
             'VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT', 'VLLM_XPU_FP16_LINEAR_CLASSPAD'):
    INVARIANT += ['--env', f'{_key}=1']


def invariant_stage(results, since, name, port, args, refs, strict_runs=0):
    """A server with the batch-invariant switch set. `refs` are this arithmetic's own no-speculation answers
    (AGENTS.md: an oracle is bound to a kernel identity); None means this stage produces them."""
    srv = R.Research(name, port, args)
    r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
    mine = {}
    if srv.ready:
        strict_ref = (refs or {}).get('strict') or REF_STRICT_OLD
        for i in range(1, strict_runs + 1):
            tag = name if i == 1 else f'{name}-run{i}'
            r['strict' if i == 1 else f'strict_run{i}'] = R.strict(srv.base, tag, strict_ref)
            R.save_results(); R.fault_check(since)
            R.log(f"{name}: strict run {i}: {r['strict' if i == 1 else f'strict_run{i}'].get('exact')} vs "
                  f"{'its own no-speculation answers' if refs else 'the SHIPPED arithmetic (expected to differ at ties)'} "
                  f"at {r['strict' if i == 1 else f'strict_run{i}'].get('tok_s_1_100')} tok/s")
        if strict_runs:
            mine['strict'] = OUT / f'{name}-strict'
        ladder = R.ladder(srv.base, name, 2)
        if ladder:
            data = json.loads(Path(ladder).read_text())
            r['passes'] = [{'repeat': b['repeat'], 'exact_vs_own_solo': f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
                            'aggregate_tok_s': round(b['aggregate_tok_s_wall'], 2)} for b in data['batches']]
            for row in r['passes']:
                R.log(f"{name}: pass {row['repeat']}: {row['exact_vs_own_solo']} equal to solo, {row['aggregate_tok_s']} tok/s together")
            if refs and refs.get('ladder'):
                r['vs_invariant_reference'] = R.ladder_compare(name, ladder, refs['ladder'])
                R.log(f"{name}: vs this arithmetic's no-speculation reference: {r['vs_invariant_reference'].get('verdict')} "
                      f"{r['vs_invariant_reference'].get('sections')}")
            mine['ladder'] = ladder
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()
    return mine


REF_STRICT_OLD = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')


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
    for port in range(18196, 18200):  # a port just released by an earlier run stays in TIME_WAIT for up to a minute
        R.wait_port_free(port)
    if os.environ.get('MU_MODE', 'screen') == 'screen':
        # first look (2026-10-04 01:22): only N requests per level, too few to call anything exact
        stage(results, since, 'tp2-mtp0-s8', 18196, TP2 + SHIPPED + ['--seqs', '8'], '2,4,8')
        stage(results, since, 'tp2-mtp5-s4', 18197, TP2 + MTP5 + SHIPPED + ['--seqs', '4'], '2,4')
    elif os.environ.get('MU_MODE') in ('long16', 'longsweep'):
        # Long prompts (2K-8K tokens): prefill and decode steps mix. No frozen reference exists for these prompts; the
        # reference is the same server's one-at-a-time answers. `long16` was the first check (16 users, shipped
        # arithmetic: NOT exact). `longsweep` asks where it becomes exact: fewer users, and the invariant switches.
        suite = ROOT / 'experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json'

        def long_stage(name, port, args):
            srv = R.Research(name, port, args)
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if srv.ready:
                out = OUT / f'{name}-concurrency.json'
                R.sh([sys.executable, R.LADDER, '--base-url', srv.base, '--model', R.MODEL_NAME, '--api-mode', 'completions',
                      '--suite', suite, '--concurrency', '64', '--repeats', '2', '--max-tokens', '128', '--seed', '42',
                      '--timeout', '3600', '--return-token-ids', '--out', out], f'{name}-concurrency', 7200)
                if out.exists():
                    data = json.loads(out.read_text())
                    r['passes'] = [{'requests_at_once': b['concurrency'], 'repeat': b['repeat'],
                                    'exact_vs_own_solo': f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
                                    'aggregate_tok_s': round(b['aggregate_tok_s_wall'], 2), 'cache_zero': b['cached_tokens_all_zero']}
                                   for b in data['batches']]
                    for row in r['passes']:
                        R.log(f"{name}: {row['requests_at_once']} sent at once, pass {row['repeat']}: {row['exact_vs_own_solo']} "
                              f"equal to solo, {row['aggregate_tok_s']} generated tok/s together, cache zero {row['cache_zero']}")
            r['stop'] = srv.stop()
            R.save_results(); R.fault_check(since); R.wait_gpus_free()

        if os.environ.get('MU_MODE') == 'long16':
            long_stage('tp2-mtp0-s16-long', 18196, TP2 + SHIPPED + ['--seqs', '16'])
        elif os.environ.get('MU_PURE') == '1':
            # the pure-step scheduling overlay: 16 users, long prompts, then the short ladder against the frozen reference
            pure = ['--overlay', 'b70-exclusive-prefill', '--extra-env', 'B70_EXCLUSIVE_PREFILL=1']
            name = 'tp2-pure-mtp0-s16'
            if os.environ.get('MU_HEAD_ROWS'):
                # second fix, from the kernel census: the LM head is the one kernel whose rounding depends on row count
                pure += ['--overlay', 'b70-lm-head-chunk', '--extra-env', f"B70_LM_HEAD_CHUNK_ROWS={os.environ['MU_HEAD_ROWS']}"]
                name = f"tp2-pure-head{os.environ['MU_HEAD_ROWS']}-mtp0-s16"
            if os.environ.get('MU_FA_PER_SEQ') == '1':
                # third fix, from the long-key census: decode attention is not batch-invariant with long keys
                pure += ['--overlay', 'b70-fa-decode-per-seq', '--extra-env', 'B70_FA_DECODE_PER_SEQ=1']
                name = name.replace('tp2-pure', 'tp2-pure-faseq')
            seqs = os.environ.get('MU_SEQS', '16')
            name = name.replace('-s16', f'-s{seqs}')
            spec = MTP5 if os.environ.get('MU_MTP') == '1' else []
            if spec:
                name = name.replace('-mtp0-', '-mtp5-')
            srv = R.Research(name, 18196, TP2 + spec + SHIPPED + pure + ['--seqs', seqs])
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if srv.ready:
                out = OUT / f'{name}-long-concurrency.json'
                R.sh([sys.executable, R.LADDER, '--base-url', srv.base, '--model', R.MODEL_NAME, '--api-mode', 'completions',
                      '--suite', suite, '--concurrency', '64', '--repeats', '2', '--max-tokens', '128', '--seed', '42',
                      '--timeout', '3600', '--return-token-ids', '--out', out], f'{name}-long-concurrency', 7200)
                if out.exists():
                    data = json.loads(out.read_text())
                    r['long'] = [{'repeat': b['repeat'], 'exact_vs_own_solo': f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
                                  'aggregate_tok_s': round(b['aggregate_tok_s_wall'], 2)} for b in data['batches']]
                    for row in r['long']:
                        R.log(f"{name}: LONG prompts, pass {row['repeat']}: {row['exact_vs_own_solo']} equal to solo, "
                              f"{row['aggregate_tok_s']} generated tok/s together")
                R.save_results(); R.fault_check(since)
                r['short'] = saturated(srv.base, name)
            r['stop'] = srv.stop()
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
        else:
            long_stage('tp2-mtp0-s4-long', 18196, TP2 + SHIPPED + ['--seqs', '4'])
            long_stage('tp2-mtp0-s8-long', 18197, TP2 + SHIPPED + ['--seqs', '8'])
            long_stage('tp2-inv-mtp0-s16-long', 18198, TP2 + SHIPPED + INVARIANT + ['--seqs', '16'])
    elif os.environ.get('MU_MODE') == 'tp1':
        # One card, no speculation, shipped arithmetic: 8 and 16 users against the one-card no-speculation reference
        # the one-card package is gated on (R310, 896-token attention block, 24,576 context).
        global REF_LADDER
        REF_LADDER = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/tp1-mtp0-b896-ladder.json')
        tp1 = ['--tp', '1', '--gpu', '0', '--mem', '0.975', '--batched', '2048', '--cpu-embed', '--fa-verify-rows',
               '--serve-arg=--block-size', '--serve-arg=896', '--max-model-len', '24576']
        for n, port in ((8, 18196), (16, 18197)):
            stage(results, since, f'tp1-mtp0-s{n}-sat', port, tp1 + ['--seqs', str(n)], 'saturated')
    elif os.environ.get('MU_MODE') == 'invariant':
        # The batch-invariant switch set as its own arithmetic: first its no-speculation answers (the reference for
        # everything after it) at 64 users, then speculation alone, at 8 and at 16 users against that reference.
        refs = invariant_stage(results, since, 'inv-mtp0-s64', 18196, TP2 + SHIPPED + INVARIANT + ['--seqs', '64'], None, strict_runs=1)
        if refs.get('ladder') and refs.get('strict') and Path(refs['strict']).exists():
            invariant_stage(results, since, 'inv-mtp5-s1', 18197, TP2 + MTP5 + SHIPPED + INVARIANT, refs, strict_runs=2)
            invariant_stage(results, since, 'inv-mtp5-s8', 18198, TP2 + MTP5 + SHIPPED + INVARIANT + ['--seqs', '8'], refs)
            invariant_stage(results, since, 'inv-mtp5-s16', 18199, TP2 + MTP5 + SHIPPED + INVARIANT + ['--seqs', '16'], refs)
        else:
            R.log('no invariant reference produced; skipping the speculation stages')
    elif os.environ.get('MU_MODE') == 'exactarm':
        # One bounded arm, not a search: depth-5 speculation at 4 users with every serial-exact switch the image
        # already has turned on. Exact or not, this is the only arm; a miss goes to an operator census, not to more arms.
        exact = []
        for key in ('VLLM_XPU_FP8_PACKED_SERIAL_EXACT', 'VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT',
                    'VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT', 'VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT',
                    'VLLM_XPU_FA_SERIAL_SPEC_DECODE', 'VLLM_XPU_LM_HEAD_BATCH_INVARIANT',
                    'VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT', 'VLLM_XPU_FP16_LINEAR_CLASSPAD'):
            exact += ['--env', f'{key}=1']
        stage(results, since, 'tp2-mtp5-s4-serialexact-sat', 18197, TP2 + MTP5 + SHIPPED + exact + ['--seqs', '4'], 'saturated')
    elif os.environ.get('MU_MODE') == 'scale':
        # how far does the lossless no-speculation profile scale? 16, 32 and 64 users
        for n, port in ((16, 18196), (32, 18197), (64, 18198)):
            stage(results, since, f'tp2-mtp0-s{n}-sat', port, TP2 + SHIPPED + ['--seqs', str(n)], 'saturated')
    else:
        # the gate: 64 prompts per pass against a server running N at a time
        stage(results, since, 'tp2-mtp0-s8-sat', 18196, TP2 + SHIPPED + ['--seqs', '8'], 'saturated')
        for n, port in ((2, 18197), (4, 18198), (8, 18199)):
            stage(results, since, f'tp2-mtp5-s{n}-sat', port, TP2 + MTP5 + SHIPPED + ['--seqs', str(n)], 'saturated')
    if os.environ.get('MU_TP1') == '1':
        stage(results, since, 'tp1-mtp0-s8', 18198, ['--tp', '1', '--gpu', '0', '--mem', '0.965', '--max-model-len', '20480',
                                                   '--batched', '4096', '--cpu-embed', '--fa-verify-rows', '--seqs', '8'], '2,4,8')
    results['finished'] = R.now()
    R.save_results()
    R.log('=== multi-user campaign complete (cards left empty) ===')


if __name__ == '__main__':
    main()
