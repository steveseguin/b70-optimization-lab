#!/usr/bin/env python3
"""The FP8 27B lossless gate set as one command, against a live endpoint, with optional evidence freezing.

Every gate compares the candidate with a same-image no-MTP reference the caller names:

  strict     the fixed 12-prompt suite (512-token answers, cache zero, canaries) vs a reference strict directory
  ladder     64 prompts one at a time, then N queued passes of the same 64, vs a reference ladder.json
  context    exact 2K/8K/16K (or given) prompts, two repeats, vs a reference context summary.json
  quality    the chat quality suite (exact cases, repeat, 8K needle) vs a reference quality.json
  history    the 21-request logprob replay (saved payloads), zero token and logprob differences

usage:
  fp8-gate-suite.py --base-url http://127.0.0.1:18124 --name tp2-candidate --out /mnt/fast-ai/bench-results/gates-x \\
      --ref-strict /path/no-mtp-strict --ref-ladder /path/no-mtp-ladder.json --ref-context /path/no-mtp-context/summary.json \\
      --ref-quality /path/no-mtp-quality.json --max-model-len 33024 [--lengths 2048,8192,16384] [--ladder-repeats 2] \\
      [--history] [--gates strict,ladder,context,quality] [--freeze experiments/.../data/<packet-dir>]

Exit code 0 only if every selected gate is exact. `--freeze` writes evidence.tar.gz + manifest.json + summary.json
(sha256 per file, sources pinned) into a repository directory so the packet can be verified without the raw root.
Owns HTTP clients only; never starts, stops or restarts a server.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]


def load_runner(out):
    os.environ['CAMPAIGN_OUT'] = str(out)
    spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def freeze(out, packet, summary, sources):
    if packet.exists():
        raise SystemExit(f'refusing to overwrite {packet}')
    files = {}
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.suffix not in ('.lock', '.tmp') and 'cache' not in path.parts and 'overlay' not in path.parts:
            files['run/' + str(path.relative_to(out))] = path.read_bytes()
    pins = []
    for name in sources:
        body = (ROOT / name).read_bytes(); files['source/' + name] = body; pins.append({'path': name, 'sha256': digest(body)})
    packet.mkdir(parents=True)
    archive = packet / 'evidence.tar.gz'
    with tarfile.open(archive, 'w:gz') as tf:
        for name, body in sorted(files.items()):
            item = tarfile.TarInfo(name); item.size = len(body); item.mode = 0o644; item.mtime = 0; tf.addfile(item, io.BytesIO(body))
    (packet / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    (packet / 'manifest.json').write_text(json.dumps({
        'schema': 'neural.download.fp8-gate-suite-evidence.v1',
        'archive': {'path': archive.name, 'sha256': digest(archive.read_bytes()), 'bytes': archive.stat().st_size},
        'summary_sha256': digest((packet / 'summary.json').read_bytes()),
        'files': [{'path': n, 'sha256': digest(b), 'bytes': len(b)} for n, b in sorted(files.items())], 'sources': pins},
        indent=2, sort_keys=True) + '\n')
    print(f'frozen {len(files)} files into {packet}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--out', type=Path, required=True, help='new raw output directory')
    ap.add_argument('--gates', default='strict,ladder,context,quality')
    ap.add_argument('--ref-strict', type=Path)
    ap.add_argument('--ref-ladder', type=Path)
    ap.add_argument('--ref-context', type=Path)
    ap.add_argument('--ref-quality', type=Path)
    ap.add_argument('--max-model-len', type=int, default=33024)
    ap.add_argument('--lengths', default='2048,8192,16384')
    ap.add_argument('--ladder-repeats', type=int, default=2)
    ap.add_argument('--history', action='store_true', help='also run the 21-request logprob replay (one-card payload set)')
    ap.add_argument('--freeze', type=Path, help='repository directory to write the frozen packet into')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    R = load_runner(a.out)
    gates = a.gates.split(',')
    results, verdicts = {'name': a.name, 'base_url': a.base_url, 'started': R.now(), 'gates': {}}, {}
    if 'strict' in gates:
        if not a.ref_strict:
            raise SystemExit('--ref-strict is required for the strict gate')
        r = R.strict(a.base_url, a.name, a.ref_strict)
        results['gates']['strict'] = r; verdicts['strict'] = r.get('exact') == '12/12' and r.get('rc') == 0
    if 'ladder' in gates:
        if not a.ref_ladder:
            raise SystemExit('--ref-ladder is required for the ladder gate')
        r = R.ladder_compare(a.name, R.ladder(a.base_url, a.name, a.ladder_repeats), a.ref_ladder)
        results['gates']['ladder'] = r; verdicts['ladder'] = r.get('verdict') == 'exact'
    if 'context' in gates:
        if not a.ref_context:
            raise SystemExit('--ref-context is required for the context gate')
        r, _ = R.context(a.base_url, a.name, a.lengths, a.max_model_len, 2, a.ref_context)
        results['gates']['context'] = r; verdicts['context'] = r.get('passed') is True
    if 'quality' in gates:
        if not a.ref_quality:
            raise SystemExit('--ref-quality is required for the quality gate')
        r, _ = R.quality(a.base_url, a.name, 2, a.ref_quality)
        results['gates']['quality'] = r; verdicts['quality'] = r.get('pass_all') is True and r.get('baseline_match_all') is True
    if a.history:
        r = R.history(a.base_url, a.name)
        results['gates']['history'] = r; verdicts['history'] = r.get('rc') == 0 and not r.get('divergent') and not r.get('logprob_divergent')
    results['verdicts'] = verdicts
    results['all_exact'] = all(verdicts.values()) and bool(verdicts)
    results['finished'] = R.now()
    (a.out / 'gate-suite.json').write_text(json.dumps(results, indent=2) + '\n')
    for gate, ok in verdicts.items():
        print(f'{gate}: {"exact" if ok else "NOT exact"}')
    print('ALL EXACT' if results['all_exact'] else 'NOT EXACT')
    if a.freeze:
        freeze(a.out, a.freeze, results, ['experiments/qwen38-27b-b70/scripts/fp8-gate-suite.py',
                                          'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py',
                                          'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py',
                                          'scripts/bench-openai-concurrency-oracle.py', 'scripts/bench-openai-realistic-suite.py',
                                          'scripts/compare-strict-attempt-outputs.py', 'scripts/neural-download-canaries.py',
                                          'scripts/qwen38-text-quality-suite.py', 'experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py',
                                          'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json',
                                          'experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json'])
    return 0 if results['all_exact'] else 1


if __name__ == '__main__':
    sys.exit(main())
