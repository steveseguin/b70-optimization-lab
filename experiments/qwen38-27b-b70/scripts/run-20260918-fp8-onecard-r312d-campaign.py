#!/usr/bin/env python3
"""One-card R312d-c acceptance campaign (2026-09-18): the staged package, all three profiles, through its own launcher.

lc-4 proved the one-pass verifier attention on a research server (every gate exact, +10-17% writing speed past 16K).
This is the promotion gate for the package update: the same checks, but driven exactly as a user drives it --
`serve.py start --profile ...` with the pinned R312d-c image and the shipped overlay set (cpu-embed, gdn-checkpoint,
fa-verify-rows and fa-multiq with B70_FA_MULTIQ_MIN_K=4096).

Stages (one stop of the two-card service, one start at the end):
  tp1-pkg-32k              `recommended`, 32,768: strict twice, the 64-prompt ladder (oracle + two queued passes),
                           the 2K/8K/16K screen on the AMD-transfer corpus vs the CKPT2 no-MTP references, chat
                           quality, the 21-request logprob replay, and the 2,048-30,720-token long corpus vs REF5;
                           then a writing-speed comparison against the R311b package's long-prompt probe
  tp1-pkg-max-context      `max-context`, 40,960: strict, ladder, the 2K/8K/16K screen
  tp1-pkg-no-quantization  `no-quantization`, 28,672: strict, ladder, the 2K/8K/16K screen
  service                  the two-card package service back on 18124, strict vs the comm-2 no-MTP reference

Every candidate is compared against the R311b 896-block no-MTP references, the same ones the shipped 32K numbers were
gated on; the census already showed the new kernel bit-identical to the untouched upstream single-row path, so a
same-image reference is not needed and a cross-image one is the stronger check.

No retry of any server; a kernel GPU fault latches the campaign and skips the restore; speed is recorded, never a gate.

Environment: SERVICE_STATE (required) is the running two-card service's state directory. B70_FP8_TP1_IMAGE defaults to
the local R312d-c tag because the image is not pushed yet -- the launcher would otherwise ask for a `docker pull` of a
digest that does not resolve. CAMPAIGN_OUT and CAMPAIGN_UNIT override the output directory and the restore unit.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
os.environ.setdefault('B70_FP8_TP1_IMAGE', 'neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r312d-c-multiq')
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path(os.environ['SERVICE_STATE'])

CKPT2 = Path('/mnt/fast-ai/bench-results/fp8-ckpt2-20260917')  # R311b no-MTP references at the 896-token attention block
REF5 = Path('/mnt/fast-ai/bench-results/fp8-probe1-20260917/tp1-mtp0-40k-context-5lengths/summary.json')
R311B_LONG = Path('/mnt/fast-ai/bench-results/fp8-probe1-20260917/tp1-pkg-max-context/summary.json')
R311B_LONG_REPO = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe1/tp1-pkg-max-context-summary.json'
COMM2_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')
PKG_TP2 = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py'
AMD_CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/corpus.json'  # the CKPT2 context baseline's corpus
LONG_CORPUS = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json'
SHORT = R.TP2_LENGTHS  # 2048,8192,16384
LONG = '2048,8192,16384,24576,30720'
PROFILES = (('tp1-pkg-32k', 'recommended', 18130, 32768),
            ('tp1-pkg-max-context', 'max-context', 18131, 40960),
            ('tp1-pkg-no-quantization', 'no-quantization', 18132, 28672))


def cgroup_memory(state_dir):
    """The container's own memory counters, read from cgroup v2 while the server is still up.

    Since 2026-09-19 both launchers run `--memory 12g --memory-swap 12g`, so the container has no swap allowance at
    all and cgroup reclaim can only drop clean file pages. That is safe exactly as long as *anonymous* memory stays
    under the ceiling: a cgroup with nothing left to reclaim OOM-kills inside itself and the server is dead at load.
    One card carries more anon than two -- B70_CPU_EMBED puts 2.368 GiB of embeddings in host memory and
    `no-quantization` builds an FP16 draft-head copy -- and the note's 8.3-8.8 GiB is arithmetic, not a measurement.
    So every profile records its own numbers: `oom_kill` must be 0, while `events.max` going up is expected and is
    the point of the change. See experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md.
    """
    state = state_dir / 'state.json'
    if not state.exists():
        return {'read': False, 'reason': 'no state receipt'}
    container = (json.loads(state.read_text()).get('container_id') or '')
    if not container:
        return {'read': False, 'reason': 'no container id in the state receipt'}
    candidates = [Path('/sys/fs/cgroup/system.slice') / f'docker-{container}.scope', Path('/sys/fs/cgroup/docker') / container]
    candidates += sorted(Path('/sys/fs/cgroup').glob(f'**/docker-{container}.scope'))
    base = next((p for p in candidates if (p / 'memory.events').exists()), None)
    if base is None:
        return {'read': False, 'reason': f'no cgroup v2 directory for container {container[:12]}', 'container_id': container}

    def pairs(name):
        try:
            return {k: int(v) for k, v in (line.split(' ', 1) for line in (base / name).read_text().splitlines() if ' ' in line)}
        except (OSError, ValueError):
            return {}

    def value(name):
        try:
            text = (base / name).read_text().strip()
        except OSError:
            return None
        return int(text) if text.isdigit() else text

    events, stat = pairs('memory.events'), pairs('memory.stat')
    anon, ceiling = stat.get('anon'), value('memory.max')
    return {'read': True, 'container_id': container, 'cgroup': str(base), 'events': events,
            'oom_kill': events.get('oom_kill'), 'oom': events.get('oom'), 'max_events': events.get('max'),
            'memory_max': ceiling, 'memory_peak': value('memory.peak'), 'memory_current': value('memory.current'),
            'swap_max': value('memory.swap.max'), 'swap_peak': value('memory.swap.peak'),
            'anon': anon, 'file': stat.get('file'), 'file_dirty': stat.get('file_dirty'),
            'pswpout': stat.get('pswpout'), 'pswpin': stat.get('pswpin'), 'pgscan_direct': stat.get('pgscan_direct'),
            'anon_headroom_bytes': (ceiling - anon) if isinstance(ceiling, int) and isinstance(anon, int) else None,
            'no_swap_configured': value('memory.swap.max') == 0, 'passed': events.get('oom_kill') == 0}


def decode_and_prefill(path):
    """Per-length medians from a bench-prefill-followup summary, plus the per-content-type writing speeds."""
    by = json.loads(Path(path).read_text())['by_length']
    return {length: {'decode_tok_s': round(row['decode_token_1_to_100_tps'], 2),
                     'prefill_tok_s': round(row['server_prefill_tokens_per_s'], 1),
                     'samples': row['samples'],
                     'decode_tok_s_by_class': {name: round(values['decode_token_1_to_100_tps'], 2)
                                               for name, values in (row.get('class_medians') or {}).items()}}
            for length, row in by.items()}


def speed_table(candidate_summary):
    """Writing speed after a long prompt, this campaign against the R311b package's probe-1 max-context run."""
    baseline_path = R311B_LONG if R311B_LONG.exists() else R311B_LONG_REPO
    if not Path(candidate_summary).exists() or not baseline_path.exists():
        return {'verdict': 'not run', 'baseline': str(baseline_path)}
    candidate, baseline = decode_and_prefill(candidate_summary), decode_and_prefill(baseline_path)
    shared = [length for length in candidate if length in baseline]
    return {'verdict': 'measured', 'baseline': str(baseline_path), 'candidate_summary': str(candidate_summary),
            'note': 'R311b reference is the probe-1 max-context profile (40,960) on the same long corpus; the short '
                    'prompts are expected to be within noise and 16K+ faster.',
            'lengths': sorted(shared, key=int),
            'r312d_c': {length: candidate[length] for length in shared},
            'r311b': {length: baseline[length] for length in shared},
            'decode_change_percent': {length: round((candidate[length]['decode_tok_s'] / baseline[length]['decode_tok_s'] - 1) * 100, 1)
                                      for length in shared}}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    since = R.now()
    R.log(f'one-card R312d-c acceptance campaign start; git '
          f'{subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}; '
          f'image {os.environ["B70_FP8_TP1_IMAGE"]}')
    results = R.RESULTS
    results['started'] = since
    results['image'] = os.environ['B70_FP8_TP1_IMAGE']
    ref = {'strict': CKPT2 / 'tp1-mtp0-b896-strict', 'ladder': CKPT2 / 'tp1-mtp0-b896-ladder.json',
           'context': CKPT2 / 'tp1-mtp0-b896-context/summary.json', 'quality': CKPT2 / 'tp1-mtp0-b896-quality.json',
           'long': REF5}
    for path in list(ref.values()) + [AMD_CORPUS, LONG_CORPUS, COMM2_STRICT, PKG_TP2]:
        if not path.exists():
            raise SystemExit(f'missing reference: {path}')
    R.save_results()
    R.stop_service()
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)

    for name, profile, port, mml in PROFILES:
        pkg = R.Package(name, profile, port)
        r = results[name] = {'profile': profile, 'max_model_len': mml,
                             'server': {k: pkg.state.get(k) for k in ('status', 'error', 'ready_at')}}
        if pkg.ready:
            r['strict'] = R.strict(pkg.base, name, ref['strict'])
            R.save_results(); R.fault_check(since)
            R.log(f"{name}: strict {r['strict'].get('exact')} at {r['strict'].get('tok_s_1_100')} tok/s")
            if profile == 'recommended':
                r['strict_run2'] = R.strict(pkg.base, f'{name}-run2', ref['strict'])
                R.save_results(); R.fault_check(since)
            r['ladder'] = R.ladder_compare(name, R.ladder(pkg.base, name, 2 if profile == 'recommended' else 1), ref['ladder'])
            R.save_results(); R.fault_check(since)
            R.CORPUS = AMD_CORPUS
            r['context'], _ = R.context(pkg.base, name, SHORT, mml, 2, ref['context'])
            R.save_results(); R.fault_check(since)
            if profile == 'recommended':
                R.CORPUS = LONG_CORPUS
                r['context_long'], _ = R.context(pkg.base, f'{name}-long', LONG, mml, 2, ref['long'])
                R.save_results(); R.fault_check(since)
                r['quality'], _ = R.quality(pkg.base, name, 2, ref['quality'])
                R.save_results(); R.fault_check(since)
                r['history'] = R.history(pkg.base, name)
                R.save_results(); R.fault_check(since)
                r['long_prompt_speed'] = speed_table(OUT / f'{name}-long-context/summary.json')
                R.log(f"{name}: long-prompt writing speed vs R311b {r['long_prompt_speed'].get('decode_change_percent')}")
            r['status_rc'] = pkg.status()
            R.log(f"{name}: run2 {r.get('strict_run2', {}).get('tok_s_1_100')}, ladder {r['ladder'].get('verdict')}, "
                  f"context {r['context'].get('passed')}, long {r.get('context_long', {}).get('passed')}, "
                  f"quality {r.get('quality', {}).get('pass_all')}/{r.get('quality', {}).get('baseline_match_all')}, "
                  f"history {r.get('history', {}).get('divergent')}/{r.get('history', {}).get('logprob_divergent')}")
        # Read before the stop: the counters die with the container. Every profile gets its own reading, because
        # `no-quantization` carries the extra FP16 draft-head copy that has never been weighed.
        r['cgroup_memory'] = cgroup_memory(pkg.out)
        R.log(f"{name}: cgroup anon {r['cgroup_memory'].get('anon')} B, headroom {r['cgroup_memory'].get('anon_headroom_bytes')} B, "
              f"max events {r['cgroup_memory'].get('max_events')}, oom_kill {r['cgroup_memory'].get('oom_kill')}, "
              f"swap.max {r['cgroup_memory'].get('swap_max')}, pswpout {r['cgroup_memory'].get('pswpout')}")
        r['stop'] = pkg.stop()
        R.save_results(); R.fault_check(since); R.wait_gpus_free()

    results['service_health_rc'] = R.health('service-health')
    R.save_results()
    if results['service_health_rc'] != 0:
        R.log('health probe failed before the service start; service left down')
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
    R.log('=== one-card R312d-c acceptance campaign complete ===')


if __name__ == '__main__':
    main()
