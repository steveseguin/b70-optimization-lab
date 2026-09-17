#!/usr/bin/env python3
"""FP8 27B review campaign, 2026-09-16: one unattended runner, one stop of the two-card service, one restore.

Preregistration: experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-campaign-prereg.md.

Stages (each a fresh server; every candidate is gated against a same-image no-MTP reference generated in this run):
  tp1-mtp0               one card, R310, no MTP: ladder oracle (64 prompts one at a time + one queued pass),
                         2K-12K context screen, chat quality suite
  tp1-pkg-recommended    the shipped package launcher, `recommended` profile: 64-prompt sequential oracle and two
                         queued 64-prompt passes vs tp1-mtp0, strict suite vs the R310 no-MTP strict run, context screen
                         vs tp1-mtp0, chat quality vs tp1-mtp0, 21-request logprob replay, clean stop through `serve.py stop`
  tp1-pkg-no-quantization the shipped `no-quantization` profile: ladder vs tp1-mtp0, strict vs no-MTP, clean stop
  tp2-mtp0               two cards, R310, no MTP: strict vs the frozen two-card control, ladder oracle, 2K-16K context
                         screen, chat quality suite
  tp2-mtp5/4/3           two cards, R310, MTP depth D + INT4 draft shortlist + decode-identical verifier rows:
                         strict, ladder, context screen, chat quality, all vs tp2-mtp0
  tp2-mtp1-shortlist     the current two-card recipe plus the draft shortlist
  tp2-mtp1-control       the current two-card recipe on R310 (same-session speed control)
  restore                health probe, then the two-card package service on 18124, strict parity vs the control

Rules honoured: no restart or retry of any server; a kernel GPU fault latches the campaign and skips the restore;
speed is recorded, never a gate; every comparison is same-image; nothing here changes power or driver state.
"""
from __future__ import annotations
import datetime as dt
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/home/steve/b70-optimization-lab')
OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-review-20260916'))
MODEL = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8')
R310 = 'sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
SHORTLIST = '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt'
LAUNCHER = ROOT / 'experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py'
PKG_TP1 = ROOT / 'packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py'
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
LADDER = ROOT / 'scripts/bench-openai-concurrency-oracle.py'
LADDER_SUITE = ROOT / 'experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json'
COMPARE_LADDER = ROOT / 'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py'
STRICT = ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh'
COMPARE_STRICT = ROOT / 'scripts/compare-strict-attempt-outputs.py'
CONTEXT = ROOT / 'experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py'
CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json'
QUALITY = ROOT / 'scripts/qwen38-text-quality-suite.py'
HISTORY = ROOT / 'experiments/qwen38-27b-b70/scripts/probe-request-history-determinism.py'
HISTORY_REQUESTS = Path('/mnt/fast-ai/bench-results/optimization-validation-20260915/fp8-tp1-25-r309-mtp0-20k-context-context')
HISTORY_SEQUENCE = ('prose-512,prose-2048,prose-12288,prose-512,code-512,docs-512,prose-2048,code-2048,docs-2048,'
                    'prose-12288,code-12288,docs-12288,code-2048,docs-2048,prose-2048,prose-2048,prose-2048,docs-12288,'
                    'prose-2048,prose-512,prose-2048')
HEALTH = ROOT / 'scripts/check-qwen36-xpu-xccl-health.sh'
XPU_PYTHON = Path.home() / '.venvs/vllm-xpu/bin/python'
TP1_MTP0_STRICT = Path('/mnt/fast-ai/bench-results/optimization-validation-20260915/fp8-tp1-54-r310-mtp0-20k-strict')
TP2_CONTROL_STRICT = Path('/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-strict')
SERVICE_STATE = Path('/mnt/fast-ai/bench-results/optimization-validation-20260916/service-restored-5')
STAGE_LOCK = Path('/tmp/qwen-short-prefill-stage.lock')
MODEL_NAME = 'qwen38-27b-fp8'
TP1_LENGTHS, TP1_MML = '2048,4096,8192,12288', 16384
TP2_LENGTHS, TP2_MML = '2048,8192,16384', 33024


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log(message):
    line = f'[review {dt.datetime.now().strftime("%m-%d %H:%M:%S")}] {message}'
    print(line, flush=True)
    with (OUT / 'campaign.log').open('a') as handle:
        handle.write(line + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load('fp8_tp2_helper', PKG_TP2)
RESULTS = {}


def save_results():
    (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2) + '\n')


def sh(argv, log_name, timeout, env=None):
    """Run one client/tool command from the repo root; record argv, rc, stdout+stderr tail."""
    (OUT / f'{log_name}.command.json').write_text(json.dumps({'argv': [str(a) for a in argv], 'started': now()}) + '\n')
    with (OUT / f'{log_name}.log').open('w') as handle:
        try:
            proc = subprocess.run([str(a) for a in argv], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                  timeout=timeout, env=dict(os.environ, **(env or {})))
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    log(f'{log_name}: rc={rc}')
    return rc


def journal_faults(since):
    text = helper.journal(since)
    return [line for line in text.splitlines() if helper.FAULT.search(line)]


def fault_check(since):
    faults = journal_faults(since)
    if faults or (OUT / 'FAULT.json').exists():
        (OUT / 'FAULT-HALT.json').write_text(json.dumps({'at': now(), 'lines': faults[-20:]}, indent=2) + '\n')
        log(f'GPU FAULT detected ({len(faults)} journal lines); campaign halted, no restore')
        raise SystemExit(3)


def docker_ps():
    return helper.run(['docker', 'ps', '-q']).stdout.split()


def wait_gpus_free(timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not docker_ps():
            with STAGE_LOCK.open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    nodes = sorted(Path('/dev/dri').glob('renderD*'))
                    busy = helper.run(['fuser', *map(str, nodes)], check=False)
                    if busy.returncode == 1 and not busy.stdout.strip():
                        return
                except BlockingIOError:
                    pass
        time.sleep(5)
    raise RuntimeError('GPUs did not become free')


def wait_port_free(port, timeout=180):
    """A stopped server's port stays in teardown for some seconds; a start inside that window fails with EADDRINUSE."""
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
                return
            except OSError:
                time.sleep(3)
    raise RuntimeError(f'port {port} did not become free')


def wait_state(state_file, proc, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state_file.exists():
            state = json.loads(state_file.read_text())
            if state.get('status') in ('ready', 'failed', 'stopped', 'stopped-before-ready'):
                return state
        if proc.poll() is not None:
            return json.loads(state_file.read_text()) if state_file.exists() else {'status': 'failed', 'error': 'exited'}
        time.sleep(5)
    return {'status': 'failed', 'error': 'startup timeout'}


class Research:
    """One research server (run-fp8-tp1-server.py --keep); stopped through its STOP file."""

    def __init__(self, name, port, args):
        self.name, self.port, self.out = name, port, OUT / name
        argv = [sys.executable, LAUNCHER, '--out', self.out, '--port', port, '--image', R310, '--warmup', '--keep',
                '--startup-timeout', '1800'] + args
        (OUT / f'{name}-owner.command.json').write_text(json.dumps({'argv': [str(a) for a in argv]}) + '\n')
        self.log = (OUT / f'{name}-owner.log').open('w')
        self.proc = subprocess.Popen([str(a) for a in argv], cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT)
        self.state = wait_state(self.out / 'state.json', self.proc, 1900)
        log(f'{name}: {self.state.get("status")} {self.state.get("error") or ""}')

    @property
    def ready(self):
        return self.state.get('status') == 'ready'

    @property
    def base(self):
        return f'http://127.0.0.1:{self.port}'

    def stop(self):
        (self.out / 'STOP').touch()
        try:
            self.proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            log(f'{self.name}: owner did not exit after STOP (left as is, no kill)')
        self.log.close()
        final = json.loads((self.out / 'state.json').read_text())
        log(f'{self.name}: final {final.get("status")} stop_confirmed={final.get("stop_confirmed")}')
        return final


class Package:
    """The shipped one-card package launcher, driven exactly as a user would."""

    def __init__(self, name, profile, port=18130):
        self.name, self.port, self.out = name, port, OUT / name
        argv = [sys.executable, PKG_TP1, 'start', '--model-dir', MODEL, '--state-dir', self.out, '--port', port,
                '--profile', profile, '--gpu', '0']
        (OUT / f'{name}-owner.command.json').write_text(json.dumps({'argv': [str(a) for a in argv]}) + '\n')
        self.log = (OUT / f'{name}-owner.log').open('w')
        self.proc = subprocess.Popen([str(a) for a in argv], cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT)
        self.state = wait_state(self.out / 'state.json', self.proc, 1900)
        log(f'{name}: {self.state.get("status")} {self.state.get("error") or ""}')

    @property
    def ready(self):
        return self.state.get('status') == 'ready'

    @property
    def base(self):
        return f'http://127.0.0.1:{self.port}'

    def status(self):
        result = helper.run([sys.executable, str(PKG_TP1), 'status', '--state-dir', str(self.out)], check=False)
        (OUT / f'{self.name}-status.json').write_text(result.stdout + result.stderr)
        return result.returncode

    def stop(self):
        result = helper.run([sys.executable, str(PKG_TP1), 'stop', '--state-dir', str(self.out)], check=False, timeout=90)
        log(f'{self.name}: stop command rc={result.returncode} {result.stderr.strip()[:200]}')
        try:
            self.proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            log(f'{self.name}: owner did not exit after stop (left as is, no kill)')
        self.log.close()
        if not (self.out / 'state.json').exists():
            return {'status': 'never started', 'error': 'no state receipt', 'container_removed': True}
        final = json.loads((self.out / 'state.json').read_text())
        gone = helper.inspect_container(final.get('container_id') or 'none') is None
        log(f'{self.name}: final {final.get("status")} error={final.get("error")} container_removed={gone}')
        return {'status': final.get('status'), 'error': final.get('error'), 'container_removed': gone}


# ---------------- tests ----------------

def ladder(base, name, repeats):
    out = OUT / f'{name}-ladder.json'
    rc = sh([sys.executable, LADDER, '--base-url', base, '--model', MODEL_NAME, '--api-mode', 'completions',
             '--suite', LADDER_SUITE, '--concurrency', '64', '--repeats', str(repeats), '--max-tokens', '128',
             '--seed', '42', '--timeout', '1800', '--return-token-ids', '--out', out], f'{name}-ladder', 4000)
    return out if out.exists() else None


def ladder_compare(name, candidate, reference):
    if not candidate or not reference:
        return {'verdict': 'not run'}
    out = OUT / f'{name}-ladder-vs-mtp0.json'
    rc = sh([sys.executable, COMPARE_LADDER, candidate, reference, '--output', out], f'{name}-ladder-compare', 300)
    if not out.exists():
        return {'verdict': 'compare failed'}
    result = json.loads(out.read_text())
    return {'verdict': 'exact' if result['all_exact'] else 'NOT exact',
            'sections': {s['section']: f"{s['exact']}/{s['total']}" for s in result['sections']},
            'first_divergences': [(m['prompt_id'], m.get('first_divergence', m.get('reason')))
                                  for s in result['sections'] for m in s['mismatches']][:12]}


def strict(base, name, reference):
    out = OUT / f'{name}-strict'
    rc = sh(['bash', STRICT], f'{name}-strict', 2400,
            env={'OUT_DIR': str(out), 'BASE_URL': base, 'MODEL_NAME': MODEL_NAME, 'PROFILE_LABEL': name,
                 'ATTEMPT_LABEL': 'review-20260916'})
    result = {'rc': rc}
    perf = out / 'performance.json'
    if perf.exists():
        summary = json.loads(perf.read_text())['summary']
        result['tok_s_1_100'] = summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
        for key in ('all_prompt_median_tok_s_1_100_intervals_after_ttft', 'class_balanced_full_completion_tok_s_wall'):
            if key in summary:
                result[key] = summary[key]['median'] if isinstance(summary[key], dict) else summary[key]
        cmp = OUT / f'{name}-strict-vs-reference.json'
        sh([sys.executable, COMPARE_STRICT, out, reference, '--output', cmp], f'{name}-strict-compare', 300)
        if cmp.exists():
            c = json.loads(cmp.read_text())['comparison']
            result['exact'] = f"{c['exact_prompts']}/{c['total_prompts']}"
            result['reference'] = str(reference)
    return result


def context(base, name, lengths, mml, repeats, baseline=None):
    out = OUT / f'{name}-context'
    argv = [sys.executable, CONTEXT, '--base-url', base, '--model', MODEL_NAME, '--out', out, '--corpus', CORPUS,
            '--lengths', lengths, '--max-model-len', str(mml), '--max-tokens', '128', '--repeats', str(repeats),
            '--timeout', '900']
    if baseline:
        argv += ['--baseline', baseline]
    rc = sh(argv, f'{name}-context', 3600)
    summary = out / 'summary.json'
    result = {'rc': rc, 'baseline': str(baseline) if baseline else None}
    if summary.exists():
        s = json.loads(summary.read_text())
        result['passed'] = s.get('passed')
        result['error'] = s.get('error')
        result['rows'] = len(s.get('rows', []))
        by = s.get('by_length') or {}
        result['by_length'] = {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()
                                   if kk in ('prefill_tok_s_median', 'decode_tok_s_median', 'median_prefill_tok_s',
                                             'median_decode_tok_s', 'ttft_s_median')}
                               for k, v in by.items()} if isinstance(by, dict) else by
    return result, (summary if result.get('passed') else None)


def quality(base, name, repeat_runs, baseline=None):
    out = OUT / f'{name}-quality.json'
    argv = [XPU_PYTHON, QUALITY, '--base-url', base, '--model', MODEL_NAME, '--tokenizer', MODEL,
            '--repeat-runs', str(repeat_runs), '--long-context-tokens', '8192',
            '--chat-template-kwargs-json', '{"enable_thinking": false}', '--output-json', out, '--timeout', '900']
    if baseline:
        argv += ['--baseline-json', baseline, '--require-baseline']
    rc = sh(argv, f'{name}-quality', 3600)
    result = {'rc': rc}
    if out.exists():
        q = json.loads(out.read_text())
        result.update(pass_all=q.get('pass_all'), baseline_match_all=q.get('baseline_match_all'),
                      baseline_status=q.get('baseline_status'))
    return result, (out if result.get('pass_all') else None)


def history(base, name):
    out = OUT / f'{name}-history'
    rc = sh([sys.executable, HISTORY, '--base-url', base, '--requests', HISTORY_REQUESTS, '--sequence', HISTORY_SEQUENCE,
             '--out', out, '--logprobs', '1', '--timeout', '900'], f'{name}-history', 2400)
    result = {'rc': rc}
    summary = out / 'summary.json'
    if summary.exists():
        s = json.loads(summary.read_text())
        result.update(divergent=s.get('divergent'), logprob_divergent=s.get('logprob_divergent'),
                      cached_tokens_all_zero=s.get('cached_tokens_all_zero'))
    return result


def health(name):
    rc = sh(['bash', HEALTH], name, 1200, env={'PYTHON': str(XPU_PYTHON)})
    return rc


# ---------------- campaign ----------------

def stop_service():
    state_file = SERVICE_STATE / 'state.json'
    if not state_file.exists():
        log('service state missing; assuming no service to stop')
        return
    state = json.loads(state_file.read_text())
    log(f'two-card service status: {state.get("status")}')
    if state.get('status') == 'starting':
        raise RuntimeError('service still starting; refusing to stop mid-load')
    if state.get('status') == 'ready':
        result = helper.run([sys.executable, str(PKG_TP2), 'stop', '--state-dir', str(SERVICE_STATE)], check=False, timeout=90)
        log(f'service stop rc={result.returncode} {result.stderr.strip()[:200]}')
        deadline = time.monotonic() + 300
        owner = state.get('owner_pid')
        while time.monotonic() < deadline and owner and Path(f'/proc/{owner}').exists():
            time.sleep(3)
    wait_gpus_free()
    log('GPUs free')


def tp1_research(name, port, args):
    return Research(name, port, ['--tp', '1', '--gpu', '0', '--mem', '0.965', '--max-model-len', '20480', '--batched', '4096',
                                 '--cpu-embed', '--fa-verify-rows'] + args)


def tp2_research(name, port, args):
    return Research(name, port, ['--tp', '2', '--mem', '0.95', '--max-model-len', str(TP2_MML), '--batched', '4096',
                                 '--fa-verify-rows'] + args)


def main():
    resume = os.environ.get('START_AT', '')  # 'tp2': skip the one-card stages and keep their recorded results
    OUT.mkdir(parents=True, exist_ok=bool(resume))
    if resume:
        RESULTS.update(json.loads((OUT / 'results.json').read_text()))
        RESULTS['resumed_at'] = {'stage': resume, 'at': now()}
    since = now()
    log(f'campaign start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    for path in (LAUNCHER, PKG_TP1, PKG_TP2, LADDER, LADDER_SUITE, COMPARE_LADDER, STRICT, COMPARE_STRICT, CONTEXT, CORPUS,
                 QUALITY, HISTORY, HISTORY_REQUESTS, HEALTH, XPU_PYTHON, TP1_MTP0_STRICT, TP2_CONTROL_STRICT, MODEL):
        if not path.exists():
            raise RuntimeError(f'missing {path}')
    image = helper.run(['docker', 'image', 'inspect', R310, '--format', '{{.Id}}'], check=False)
    if image.stdout.strip() != R310:
        raise RuntimeError('R310 image missing')
    RESULTS['started'] = since
    save_results()

    stop_service()
    RESULTS['preflight_health_rc'] = health('preflight-health')
    save_results()
    if RESULTS['preflight_health_rc'] != 0:
        log('preflight health probe failed; halting before any server')
        raise SystemExit(4)
    fault_check(since)

    # ---- one card, no MTP reference
    if resume == 'tp2':
        log('resuming at the two-card stages; one-card results kept from the earlier run')
    ref = None if resume == 'tp2' else tp1_research('tp1-mtp0', 18140, ['--mtp', '0'])
    tp1_ladder = tp1_ctx = tp1_quality = None
    reuse = Path(os.environ['REUSE_TP1_LADDER']) if os.environ.get('REUSE_TP1_LADDER') else None
    if ref is None:
        pass
    elif ref.ready:
        tp1_ladder = reuse if reuse and reuse.exists() else ladder(ref.base, 'tp1-mtp0', 1)
        RESULTS['tp1-mtp0'] = {'context': None, 'quality': None}
        RESULTS['tp1-mtp0']['context'], tp1_ctx = context(ref.base, 'tp1-mtp0', TP1_LENGTHS, TP1_MML, 2)
        RESULTS['tp1-mtp0']['quality'], tp1_quality = quality(ref.base, 'tp1-mtp0', 1)
        RESULTS['tp1-mtp0']['ladder'] = str(tp1_ladder) if tp1_ladder else None
    else:
        RESULTS['tp1-mtp0'] = {'server': ref.state}
    if ref is not None:
        RESULTS['tp1-mtp0']['stop'] = ref.stop()
    save_results()
    fault_check(since)
    wait_gpus_free()

    # ---- the shipped one-card package, both profiles
    # Distinct ports: a port is still in teardown for a few seconds after the previous server stops.
    profiles = [] if resume == 'tp2' else [('tp1-pkg-recommended', 'recommended', 18130),
                                           ('tp1-pkg-no-quantization', 'no-quantization', 18131)]
    for name, profile, port in profiles:
        pkg = Package(name, profile, port)
        r = RESULTS[name] = {'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if pkg.ready:
            r['ladder'] = ladder_compare(name, ladder(pkg.base, name, 2 if profile == 'recommended' else 1), tp1_ladder)
            r['strict'] = strict(pkg.base, name, TP1_MTP0_STRICT)
            if profile == 'recommended':
                r['context'], _ = context(pkg.base, name, TP1_LENGTHS, TP1_MML, 2, tp1_ctx)
                r['quality'], _ = quality(pkg.base, name, 2, tp1_quality)
                r['history'] = history(pkg.base, name)
            r['status_rc'] = pkg.status()
        r['stop'] = pkg.stop()
        save_results()
        fault_check(since)
        wait_gpus_free()

    # ---- two cards, no MTP reference on R310
    ref2 = tp2_research('tp2-mtp0', 18141, ['--mtp', '0'])
    tp2_ladder = tp2_ctx = tp2_quality = None
    tp2_strict_ref = OUT / 'tp2-mtp0-strict'
    if ref2.ready:
        RESULTS['tp2-mtp0'] = {'strict': strict(ref2.base, 'tp2-mtp0', TP2_CONTROL_STRICT)}
        tp2_ladder = ladder(ref2.base, 'tp2-mtp0', 1)
        RESULTS['tp2-mtp0']['context'], tp2_ctx = context(ref2.base, 'tp2-mtp0', TP2_LENGTHS, TP2_MML, 2)
        RESULTS['tp2-mtp0']['quality'], tp2_quality = quality(ref2.base, 'tp2-mtp0', 1)
        RESULTS['tp2-mtp0']['ladder'] = str(tp2_ladder) if tp2_ladder else None
    else:
        RESULTS['tp2-mtp0'] = {'server': ref2.state}
    RESULTS['tp2-mtp0']['stop'] = ref2.stop()
    save_results()
    fault_check(since)
    wait_gpus_free()
    if not (tp2_strict_ref / 'performance.json').exists():
        tp2_strict_ref = None

    # ---- two-card candidates
    candidates = [('tp2-mtp5', ['--mtp', '5', '--draft-int4', '--shortlist', SHORTLIST]),
                  ('tp2-mtp4', ['--mtp', '4', '--draft-int4', '--shortlist', SHORTLIST]),
                  ('tp2-mtp3', ['--mtp', '3', '--draft-int4', '--shortlist', SHORTLIST]),
                  ('tp2-mtp1-shortlist', ['--mtp', '1', '--draft-int4', '--shortlist', SHORTLIST]),
                  ('tp2-mtp1-control', ['--mtp', '1', '--draft-int4'])]
    for index, (name, args) in enumerate(candidates):
        srv = tp2_research(name, 18142 + index, args)
        r = RESULTS[name] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if srv.ready:
            r['strict'] = strict(srv.base, name, tp2_strict_ref) if tp2_strict_ref else {'verdict': 'no reference'}
            r['ladder'] = ladder_compare(name, ladder(srv.base, name, 2), tp2_ladder)
            r['context'], _ = context(srv.base, name, TP2_LENGTHS, TP2_MML, 2, tp2_ctx)
            r['quality'], _ = quality(srv.base, name, 1, tp2_quality)
        r['stop'] = srv.stop()
        save_results()
        fault_check(since)
        wait_gpus_free()

    # ---- restore the two-card service as its own unit so it outlives this runner
    RESULTS['restore_health_rc'] = health('restore-health')
    save_results()
    if RESULTS['restore_health_rc'] != 0:
        log('health probe failed before restore; service left down')
        raise SystemExit(5)
    state_dir = OUT / 'service-restored-6'
    unit = 'fp8-service-20260916'
    argv = ['systemd-run', '--user', '--unit', unit, '--working-directory', str(ROOT), '--collect',
            sys.executable, str(PKG_TP2), 'start', '--model-dir', str(MODEL), '--state-dir', str(state_dir), '--port', '18124']
    wait_port_free(18124)
    (OUT / 'restore.command.json').write_text(json.dumps({'argv': argv, 'started': now()}) + '\n')
    subprocess.run(argv, check=True)
    deadline = time.monotonic() + 2400
    state = {}
    while time.monotonic() < deadline:
        if (state_dir / 'state.json').exists():
            state = json.loads((state_dir / 'state.json').read_text())
            if state.get('status') in ('ready', 'failed', 'stopped'):
                break
        time.sleep(10)
    RESULTS['restore'] = {'status': state.get('status'), 'error': state.get('error'), 'unit': unit, 'state_dir': str(state_dir)}
    log(f'restore: {state.get("status")} {state.get("error") or ""}')
    if state.get('status') == 'ready':
        RESULTS['restore']['strict'] = strict('http://127.0.0.1:18124', 'service-restored-6', TP2_CONTROL_STRICT)
    save_results()
    fault_check(since)
    RESULTS['finished'] = now()
    save_results()
    log('=== campaign complete ===')


if __name__ == '__main__':
    main()
