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
import datetime as dt
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

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
# Runtime (compute-runtime) debug keys are read only with NEOReadDebugKeys=1 (used for its allocation log).
# The load-fault fix: CPU-to-card copies over 256 MiB go in 128 MiB pieces during model load, so the runtime never makes
# the temporary host mapping the fault hits. (The runtime's own switch, ExperimentalH2DCpuCopyThreshold, was tried first
# and has no effect here: the card-side memory is not the kind its CPU-copy path accepts.)
CLASSPAD = ['--env', 'VLLM_XPU_FP16_LINEAR_CLASSPAD=1']
NEO_KEYS = ['--extra-env', 'NEOReadDebugKeys=1']
# one-at-a-time, speculation-off answers to the long suite (the oracle pass of the 64-user run of 2026-10-04)
LONG_REF = Path('/mnt/fast-ai/bench-results/fp8-multiuser-three-s64-20261004/tp2-pure-faseq-head4-mtp0-s64-long-concurrency.json')
LOADCOPY_FIX = ['--overlay', 'b70-chunked-upload', '--extra-env', 'B70_CHUNKED_UPLOAD=1']


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


def kernel_log(*extra):
    return subprocess.run(['journalctl', '-k', '-b', '--no-pager', *extra], capture_output=True, text=True).stdout


def start_server(name, port, args, since):
    """Start one research server. If it hits the known model-load fault, and that is the first fault on this boot,
    recover once the way AGENTS.md says (stop, health probe, one fresh start). Returns (server, name, since)."""
    R.wait_port_free(port)  # a port just released by the previous server stays in TIME_WAIT for up to a minute
    if os.environ.get('MU_IMAGE'):  # a research image other than R310 (the launcher takes the last --image)
        args = list(args) + ['--image', os.environ['MU_IMAGE']]
    if os.environ.get('MU_SPEC_RESUME') == '1':
        # engine fix: a request that sat out a step keeps the accepted-token count the recurrent layers need
        args = list(args) + ['--overlay', 'b70-spec-resume-accepted', '--extra-env', 'B70_SPEC_RESUME_ACCEPTED=1']
    for item in os.environ.get('MU_EXTRA_ENV', '').split():  # research probes: extra KEY=VALUE for the server
        args = list(args) + ['--extra-env', item]
    if os.environ.get('MU_STATE_WIDTH') == '1':
        # engine fix for the recurrent layers' state-slot table (needs the R314 kernel): a step narrower than the tokens
        # just accepted no longer reads past the end of the table
        args = list(args) + ['--overlay', 'b70-gdn-state-width', '--extra-env', 'B70_GDN_STATE_WIDTH=1']
    srv = R.Research(name, port, args)
    lines = R.journal_faults(since)
    if not lines:
        return srv, name, since
    spec = importlib.util.spec_from_file_location('lfr', ROOT / 'experiments/qwen38-27b-b70/scripts/load_fault_recovery.py')
    lfr = importlib.util.module_from_spec(spec); spec.loader.exec_module(lfr)
    local = dt.datetime.fromisoformat(since).astimezone().strftime('%Y-%m-%d %H:%M:%S')
    text = kernel_log('-o', 'cat', '--since', local)
    (OUT / f'{name}-load-fault-records.txt').write_text(text)
    boot_lines = [line for line in kernel_log().splitlines() if R.FAULT.search(line)]
    action, reason = lfr.decide(srv.ready, lfr.parse_records(text), len(lines), len(boot_lines))
    R.log(f'{name}: GPU fault during start ({len(lines)} lines): {action}: {reason}')
    if action != 'recover':
        srv.stop()
        R.fault_check(since)  # writes FAULT-HALT.json and exits
    final = srv.stop()
    R.wait_gpus_free()
    time.sleep(60)  # quiet period before touching the cards again
    after = R.now()
    rc = R.health(f'{name}-recovery-health')
    again = R.journal_faults(after)
    (OUT / 'LOAD-FAULT-RECOVERY.json').write_text(json.dumps({
        'at': after, 'server': name, 'fault_lines': len(lines), 'stopped': final.get('status'), 'health_rc': rc,
        'fault_lines_after_stop': len(again), 'note': 'device dump not copied (root only); copy it within the hour'}, indent=2) + '\n')
    if rc != 0 or again:
        R.log(f'{name}: recovery refused: health rc={rc}, {len(again)} new fault lines')
        R.fault_check(since)
    latch = OUT / 'FAULT.json'  # the launcher's own latch; kept as a receipt under another name
    if latch.exists():
        latch.rename(OUT / f'FAULT-recovered-{name}.json')
    R.log(f'{name}: health probe passed after the load fault; one fresh start')
    R.wait_port_free(port)
    retry = f'{name}-retry'
    return R.Research(retry, port, args), retry, after


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
    if os.environ.get('MU_MODE') == 'serve_run':
        # Context experiments: one two-card server with a chosen window (and tool calling for agent harnesses), kept up
        # while a client script runs against it, then stopped. MU_RUN_SCRIPT gets API_BASE, BASE_URL and OUT_DIR.
        mml = os.environ.get('MU_LONG_MML', '65536')
        wide = ['--tp', '2', '--mem', '0.95', '--max-model-len', mml, '--batched', os.environ.get('MU_BATCHED', '4096'), '--fa-verify-rows']
        spec = [] if os.environ.get('MU_MTP') == '0' else MTP5
        serve = [f'--serve-arg={x}' for x in os.environ.get('MU_SERVE_ARGS', '').split()]
        extra = os.environ.get('MU_LAUNCH_ARGS', '').split()
        tag = os.environ.get('MU_RUN_NAME', 'ctx')
        srv, name, since = start_server(f'tp2-{tag}-w{mml}', 18196, wide + spec + SHIPPED + LOADCOPY_FIX + serve + extra, since)
        r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            client = OUT / 'client'
            client.mkdir(exist_ok=True)
            r['client_rc'] = R.sh(['bash', os.environ['MU_RUN_SCRIPT']], f'{name}-client', int(os.environ.get('MU_RUN_TIMEOUT', '14400')),
                                  env={'API_BASE': srv.base + '/v1', 'BASE_URL': srv.base, 'OUT_DIR': str(client),
                                       'MODEL_NAME': R.MODEL_NAME})
            R.log(f"{name}: client script finished rc={r['client_rc']}")
        r['stop'] = srv.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()
    elif os.environ.get('MU_MODE') == 'longctx':
        # A window far beyond 33K, with the full 16-bit cache: the model has 262,144 trained positions and the two-card
        # cache pool holds about 268,000 tokens. One user, drafting on and off (two servers), the ledger probe at
        # growing lengths; the two servers' answers are compared token for token.
        # notes/2026-10-05-context-window-prereg.md
        mml = os.environ.get('MU_LONG_MML', '262144')
        lengths = os.environ.get('MU_LONG_LENGTHS', '8000,30000,60000,120000,200000,250000')
        wide = ['--tp', '2', '--mem', '0.95', '--max-model-len', mml, '--batched', '4096', '--fa-verify-rows']
        probe = ROOT / 'experiments/qwen38-27b-b70/scripts/qwen38-fp8-long-context-probe.py'
        answers = {}
        for label, spec in (('mtp5', MTP5), ('mtp0', [])):
            if label == 'mtp0' and os.environ.get('MU_LONG_CONTROL', '1') != '1':
                continue
            srv, name, since = start_server(f'tp2-long{mml}-{label}', 18196, wide + spec + SHIPPED + LOADCOPY_FIX, since)
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if srv.ready:
                out = OUT / f'{name}-probe.json'
                R.sh([str(R.XPU_PYTHON), probe, '--base-url', srv.base, '--model', R.MODEL_NAME, '--lengths', lengths,
                      '--out', out], f'{name}-probe', 4 * 3600)
                if out.exists():
                    rows = json.loads(out.read_text())['rows']
                    r['probe'] = [{k: row.get(k) for k in ('target_tokens', 'prompt_tokens_client', 'ttft_s', 'prompt_read_tok_s',
                                                             'decode_tok_s', 'all_correct', 'in_order', 'error')} for row in rows]
                    answers[label] = {row['target_tokens']: row.get('token_ids') for row in rows}
                    for row in rows:
                        R.log(f"{name}: {row['target_tokens']} tokens: " + (row['error'][:120] if row.get('error') else
                              f"first token {row['ttft_s']:.1f} s, reads {row['prompt_read_tok_s']:.0f} tok/s, writes "
                              f"{row['decode_tok_s'] and round(row['decode_tok_s'], 1)} tok/s, codes right {row['all_correct']}"))
            if srv.ready and label == 'mtp5' and os.environ.get('MU_LONG_CHOICE', '1') == '1':
                # track 4, same server: decisions read from the first step against decoding them (CPU client)
                out = OUT / f'{name}-choice.json'
                R.sh([str(R.XPU_PYTHON), ROOT / 'experiments/qwen38-27b-b70/scripts/qwen38-fp8-one-step-choice-probe.py',
                      '--base-url', srv.base, '--model', R.MODEL_NAME, '--out', out], f'{name}-choice', 3600)
                if out.exists():
                    r['choice'] = json.loads(out.read_text()).get('summary')
                    R.log(f"{name}: one-step choices: {json.dumps(r['choice'])[:600]}")
            r['stop'] = srv.stop()
            text = (OUT / name / 'server.log').read_text(errors='replace') if (OUT / name / 'server.log').exists() else ''
            r['kv_lines'] = re.findall(r'GPU KV cache size[^\n]*', text)[:2]
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
        if 'mtp5' in answers and 'mtp0' in answers:
            same = {n: answers['mtp5'].get(n) == answers['mtp0'].get(n) and answers['mtp5'].get(n) is not None for n in answers['mtp5']}
            results['drafting_equal_to_no_drafting'] = same
            R.log(f'answers with drafting equal to answers without, by length: {same}')
            R.save_results()
    elif os.environ.get('MU_MODE') == 'syncprobe':
        # What does the synchronous step pipeline cost one user on the shipped recipe? (A per-step draft length, which
        # longer copy drafts need, is natural there: the scheduler takes each request's draft as a list every step.)
        for label, extra in (('async', []), ('sync', ['--serve-arg=--no-async-scheduling'])):
            srv, name, since = start_server(f'tp2-mtp5-{label}', 18196, TP2 + MTP5 + SHIPPED + LOADCOPY_FIX + extra, since)
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if srv.ready:
                r['strict'] = R.strict(srv.base, name, R.TP2_CONTROL_STRICT)
                r['strict_run2'] = R.strict(srv.base, f'{name}-run2', R.TP2_CONTROL_STRICT)
                R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} and "
                      f"{r['strict_run2'].get('exact')} at {r['strict_run2'].get('tok_s_1_100')} tok/s")
            r['stop'] = srv.stop()
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
    elif os.environ.get('MU_MODE') == 'copydraft':
        # One user, shipped two-card recipe, with and without copy-from-context drafts (b70-copy-draft). Gates against
        # the frozen references; speed on the long suite as the per-request decode rate after the first token.
        # notes/2026-10-04-copy-draft-sizing-prereg.md
        suite = str(ROOT / 'experiments/qwen38-27b-b70/data/2026-10-04-fp8-multiuser/long-prompt-suite.json')
        copy = ['--overlay', 'b70-copy-draft', '--extra-env', 'B70_COPY_DRAFT=1']
        for extra in os.environ.get('MU_COPY_ENV', '').split():
            copy += ['--extra-env', extra]
        deep, tag = [], ''
        if os.environ.get('MU_COPY_K'):
            # longer copy drafts: K verify slots reserved, the head still drafts 5 (the stock per-batch-size schedule),
            # synchronous pipeline so each request's draft is a per-step list. Both arms get the same launch; only
            # the copy arm lets a copy draft use more than 5 tokens.
            k = int(os.environ['MU_COPY_K'])
            deep = ['--serve-arg=--no-async-scheduling', '--spec-config-json', json.dumps({
                'method': 'qwen3_next_mtp', 'num_speculative_tokens': k, 'num_speculative_tokens_per_batch_size': [[1, 1, 5]]})]
            copy = copy + ['--extra-env', f'B70_COPY_DRAFT_K_MAX={k}']
            tag = f'-sync-k{k}'
        arms = (('control', []), ('copy', copy)) if os.environ.get('MU_COPY_CONTROL', '1') == '1' else (('copy', copy),)
        for label, extra in arms:
            srv, name, since = start_server(f'tp2-mtp5{tag}-{label}', 18196, TP2 + MTP5 + SHIPPED + LOADCOPY_FIX + deep + extra, since)
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if srv.ready:
                r['strict'] = R.strict(srv.base, name, R.TP2_CONTROL_STRICT)
                R.log(f"{name}: strict {r['strict'].get('exact')} exact, {r['strict'].get('tok_s_1_100')} tok/s")
                R.save_results(); R.fault_check(since)
                out = OUT / f'{name}-long.json'
                R.sh([sys.executable, R.LADDER, '--base-url', srv.base, '--model', R.MODEL_NAME, '--api-mode', 'completions',
                      '--suite', suite, '--concurrency', '8', '--repeats', '1', '--max-tokens', '128', '--seed', '42',
                      '--timeout', '3600', '--return-token-ids', '--out', out], f'{name}-long', 7200)
                if out.exists():
                    rows = json.loads(out.read_text())['oracle']['rows']
                    rates = sorted(x['tok_s_after_ttft_full'] for x in rows if x.get('tok_s_after_ttft_full'))
                    ref_rows = json.loads(LONG_REF.read_text())['oracle']['rows'] if LONG_REF.exists() else []
                    # the tool makes every request distinct (prompt-cNNN), so answers are matched by the full id
                    ref = {x['prompt_id']: x['token_ids'] for x in ref_rows}
                    same = [ref.get(x['prompt_id']) == x['token_ids'] for x in rows]
                    R.log(f"{name}: long suite vs the no-speculation answers of 2026-10-04: {sum(same)}/{len(same)} identical")
                    r['long_vs_no_speculation'] = f'{sum(same)}/{len(same)}'
                    r['long'] = {'requests': len(rows), 'decode_tok_s_median': rates[len(rates) // 2] if rates else None,
                                 'decode_tok_s_mean': sum(rates) / len(rates) if rates else None,
                                 'token_sha': [x['sha256'] for x in rows]}
                    R.log(f"{name}: long suite, {len(rows)} requests, decode after first token: median "
                          f"{r['long']['decode_tok_s_median']:.1f} tok/s, mean {r['long']['decode_tok_s_mean']:.1f}")
                R.save_results(); R.fault_check(since)
                r['short'] = saturated(srv.base, name)
            r['stop'] = srv.stop()
            text = (OUT / name / 'server.log').read_text(errors='replace') if (OUT / name / 'server.log').exists() else ''
            r['copy_draft_lines'] = re.findall(r'b70_copy_draft: [^\n]*', text)[-6:]
            for line in r['copy_draft_lines']:
                R.log(f'{name}: {line[:200]}')
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
        a, b = results.get(f'tp2-mtp5{tag}-control', {}).get('long'), results.get(f'tp2-mtp5{tag}-copy', {}).get('long')
        if a and b:
            R.log(f"long suite answers identical between the arms: {a['token_sha'] == b['token_sha']}; decode median "
                  f"{a['decode_tok_s_median']:.1f} -> {b['decode_tok_s_median']:.1f} tok/s "
                  f"({(b['decode_tok_s_median'] / a['decode_tok_s_median'] - 1) * 100:+.1f}%)")
    elif os.environ.get('MU_MODE') == 'loadcopy':
        # The model-load fault is the copy engine reading a temporary mapping of host memory (every host-to-card copy
        # of 512 MiB or more gets one, at GPU address 0x800400200000; 256 MiB or less does not). The chunked-upload
        # overlay sends the large tensors in 128 MiB pieces. Two starts of the shipped two-card server: the runtime's
        # allocation log with the overlay, then the overlay alone with the strict gate.
        # notes/2026-10-04-gpu-fault-mtp-start.md has the reading and the rule.
        debug = []
        for key in ('LogAllocationType', 'LogAllocationStdout', 'PrintBOBindingResult', 'PrintBOCreateDestroyResult'):
            debug += ['--extra-env', f'{key}=1']
        stages = (('chunked-log', NEO_KEYS + LOADCOPY_FIX + debug, False), ('chunked', LOADCOPY_FIX, True))
        if os.environ.get('MU_LOADCOPY_CONTROL') == '1':  # the log without the fix (done twice on 2026-10-04: 8 mappings each)
            stages = (('control-log', NEO_KEYS + debug, False),) + stages
        # MU_LOADCOPY_TP=1: the one-card research server (speculation off), whose output-layer weight is 2.5 GB
        one_card = os.environ.get('MU_LOADCOPY_TP') == '1'
        base = (['--tp', '1', '--gpu', '0', '--mem', '0.965', '--max-model-len', '20480', '--batched', '4096', '--cpu-embed',
                 '--fa-verify-rows'] if one_card else TP2 + MTP5 + SHIPPED)
        reference, prefix = (R.TP1_MTP0_STRICT, 'tp1') if one_card else (R.TP2_CONTROL_STRICT, 'tp2')
        for label, extra, gate in stages:
            srv, name, since = start_server(f'{prefix}-loadcopy-{label}', 18196, base + extra, since)
            r = results[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
            if gate and srv.ready:
                r['strict'] = R.strict(srv.base, name, reference)
                R.log(f"{name}: strict {r['strict'].get('exact')} exact, {r['strict'].get('tok_s_1_100')} tok/s")
            r['stop'] = srv.stop()
            text = (OUT / name / 'server.log').read_text(errors='replace') if (OUT / name / 'server.log').exists() else ''
            lines = text.splitlines()
            at_address = [line for line in lines if re.search(r'8004002[0-9a-f]{5}', line, re.I)]
            host_ptr = [line for line in lines if re.search(r'external.?host.?ptr', line, re.I)]
            r['load_seconds'] = [float(x) for x in re.findall(r'Loading weights took ([0-9.]+) seconds', text)]
            r['chunked_upload_lines'] = re.findall(r'b70_chunked_upload: [^\n]*', text)[:4]
            r['log_lines'], r['lines_at_fault_address'], r['host_pointer_lines'] = len(lines), len(at_address), len(host_ptr)
            (OUT / f'{name}-fault-address-lines.txt').write_text('\n'.join((at_address + host_ptr)[:600]) + '\n')
            R.log(f"{name}: {r['server']['status']}; load {r['load_seconds']} s; {len(at_address)} log lines at the fault "
                  f"address, {len(host_ptr)} host-pointer lines, {len(lines)} lines in all")
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
    elif os.environ.get('MU_MODE', 'screen') == 'screen':
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
            if os.environ.get('MU_PREFILL_BATCH'):  # several short new prompts per prompt-only step (research)
                pure += ['--extra-env', f"B70_EXCLUSIVE_PREFILL_BATCH={os.environ['MU_PREFILL_BATCH']}"]
            name = 'tp2-pure-mtp0-s16'
            if os.environ.get('MU_HEAD_ROWS'):
                # second fix, from the kernel census: the LM head is the one kernel whose rounding depends on row count
                pure += ['--overlay', 'b70-lm-head-chunk', '--extra-env', f"B70_LM_HEAD_CHUNK_ROWS={os.environ['MU_HEAD_ROWS']}"]
                name = f"tp2-pure-head{os.environ['MU_HEAD_ROWS']}-mtp0-s16"
                if os.environ.get('MU_HEAD_AT') == 'head':
                    # same per-rank head calls, chunked before the card-to-card gather: one gather per step
                    pure += ['--extra-env', 'B70_LM_HEAD_CHUNK_AT=head']
                    name = name.replace('-head', '-headlocal')
            if os.environ.get('MU_FA_PER_SEQ') == '1':
                # third fix, from the long-key census: decode attention is not batch-invariant with long keys
                pure += ['--overlay', 'b70-fa-decode-per-seq', '--extra-env', 'B70_FA_DECODE_PER_SEQ=1']
                name = name.replace('tp2-pure', 'tp2-pure-faseq')
            seqs = os.environ.get('MU_SEQS', '16')
            name = name.replace('-s16', f'-s{seqs}')
            if os.environ.get('MU_PREFILL_BATCH'):
                name = name.replace('tp2-', f"tp2-pb{os.environ['MU_PREFILL_BATCH']}-", 1)
            spec = MTP5 if os.environ.get('MU_MTP') == '1' else []
            if spec:
                name = name.replace('-mtp0-', '-mtp5-')
            if os.environ.get('MU_CLASSPAD') == '1':
                # only the output layer's row class is fixed (the image pads every FP16 linear call, a lone user's
                # included, into one census-verified row class); everything else is the shipped arithmetic
                pure += CLASSPAD
                name = name.replace('tp2-pure', 'tp2-cp-pure')
            if os.environ.get('MU_INVARIANT') == '1':
                # the image's own batch-invariant arithmetic (output layer padded to one row class, serial-exact
                # speculative kernels). Its lone-user answers differ from the shipped recipe's at exact ties, so the
                # gate that matters here is "equal to solo on this same server", not the frozen reference.
                pure += INVARIANT
                name = name.replace('tp2-pure', 'tp2-inv-pure')
            if os.environ.get('MU_LOADCOPY_FIX', '1') == '1':  # validated on R310 two-card, 2026-10-04 11:07 EDT
                pure += LOADCOPY_FIX
            srv, name, since = start_server(name, 18196, TP2 + spec + SHIPPED + pure + ['--seqs', seqs], since)
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
    elif os.environ.get('MU_MODE') == 'classpad':
        # One arithmetic for one user and for many: the class-padded output layer. First its no-speculation answers
        # (the reference for this arithmetic), then the shipped depth-5 speculation for one user against them.
        refs = invariant_stage(results, since, 'cp-mtp0-s1', 18196, TP2 + SHIPPED + LOADCOPY_FIX + CLASSPAD, None, strict_runs=1)
        if refs.get('ladder') and refs.get('strict') and Path(refs['strict']).exists():
            invariant_stage(results, since, 'cp-mtp5-s1', 18197, TP2 + MTP5 + SHIPPED + LOADCOPY_FIX + CLASSPAD, refs, strict_runs=2)
        else:
            R.log('no class-pad reference produced; skipping the speculation stage')
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
