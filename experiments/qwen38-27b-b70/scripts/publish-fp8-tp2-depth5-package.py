#!/usr/bin/env python3
"""Update the two-card FP8 package manifest to the R310 depth-5 recipe from the review-campaign receipts.

Reads experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/results.json (copied by publish-fp8-review-receipts.py)
and, when present, the frozen acceptance packet summary. Rewrites only the manifest fields that describe the
recommended setup; historical profiles and contributor records stay.

usage: publish-fp8-tp2-depth5-package.py [--acceptance experiments/.../2026-09-17-fp8-two-card-depth5/summary.json]
"""
import argparse
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp2-b70/package.json'
DATA = 'experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/'
R310 = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
NEW_DEPENDENCIES = [
    'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
    'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py',
    'packages/qwen38-27b-fp8-tp2-b70/compose.yaml',
    'packages/qwen38-27b-fp8-tp2-b70/scripts/render-compose.sh',
    'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md',
    'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-campaign-prereg.md',
    'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py',
    'experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py',
    'experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py',
    'experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py',
    'experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch',
    'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch',
    'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r310-gdn-barriers',
    'experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r310-gdn-barriers.sh',
    DATA + 'results.json',
    DATA + 'tp2-mtp5-strict-performance.json', DATA + 'tp2-mtp5-strict-vs-reference.json',
    DATA + 'tp2-mtp5-context-summary.json', DATA + 'tp2-mtp5-ladder-vs-mtp0.json', DATA + 'tp2-mtp5-quality.json',
    DATA + 'tp2-mtp0-strict-performance.json', DATA + 'tp2-mtp0-strict-vs-reference.json',
    DATA + 'tp2-mtp0-context-summary.json', DATA + 'tp2-mtp0-ladder.json',
    DATA + 'tp2-mtp4-strict-performance.json', DATA + 'tp2-mtp3-strict-performance.json',
    DATA + 'tp2-mtp1-shortlist-strict-performance.json', DATA + 'tp2-mtp1-control-strict-performance.json',
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--acceptance', type=Path)
    a = ap.parse_args()
    results = json.loads((ROOT / DATA / 'results.json').read_text())
    first = results['tp2-mtp5']['strict']['tok_s_1_100']
    depth1 = results['tp2-mtp1-control']['strict']['tok_s_1_100']
    no_mtp = results['tp2-mtp0']['strict']['tok_s_1_100']
    package = json.loads(PACKAGE.read_text())
    lib = package['library']
    pair = [first]
    acceptance_note = ('The public-source acceptance replay of this launcher, the second fresh server, is pending; the '
                       'featured rate is one fresh server until it lands.')
    if a.acceptance:
        summary = json.loads(a.acceptance.read_text())
        assert summary['passed'], summary['gates']
        pair.append(summary['strict']['decode_tokens_s'])
        acceptance_note = (f"The public-source acceptance replay through this launcher measured "
                           f"{pair[1]:.2f} tok/s with 12/12 outputs identical to no MTP, six practical requests with exact repeats, "
                           f"and a clean stop (commit {summary['public_source_commit'][:9]}).")
    lib['summary'] = ('Official Qwen FP8 weights on two Intel Arc Pro B70 cards. Recommended: one user, MTP depth 5 with a '
                      'draft-only INT4 shortlist head, 33,024 total tokens (a 32K input plus 256 for the answer), '
                      f'{statistics.median(pair):.1f} tok/s writing speed; outputs identical to no MTP. A depth-1 profile keeps the '
                      'September 14 recipe.')
    lib['public_summary'] = lib['summary']
    lib['benchmark_status'] = (f'September 16 review campaign on the R310 runtime: depth 5 measured {first:.2f} tok/s on a fresh '
                               f'server, 12/12 identical to no MTP on the strict suite, 64/64 on the 64-prompt sequential oracle plus '
                               f'two queued passes, exact after 2K/8K/16K prompts and on the chat quality suite; depths 3 and 4 and the '
                               f'depth-1 profile ({depth1:.2f} tok/s) passed the same gates. {acceptance_note} Clean-host install and '
                               'multiple users are untested.')
    lib['tags'] = ['two cards', 'Docker', 'official checkpoint', 'MTP depth 5', 'lossless', 'deterministic', '32K input']
    lib['featured_metric'] = {
        'value': statistics.median(pair), 'unit': 'tok/s', 'label': 'Writing speed · MTP depth 5 · two cards',
        'scope': (f'{"Median of two" if len(pair) == 2 else "One"} fresh R310 two-card server{"s" if len(pair) == 2 else ""} '
                  f'({" / ".join(f"{v:.3f}" for v in pair)}) at a 33,024-token context on the fixed 12-prompt six-class suite, '
                  '512-token answers, class-balanced median of tokens 1-100, cache zero, canaries passed, 12/12 complete outputs '
                  f'identical to no-MTP decoding ({no_mtp:.2f} tok/s on the same image), 64/64 on the sequential oracle.'),
        'evidence': DATA + 'tp2-mtp5-strict-performance.json'}
    package['runtime'] = {
        'kind': 'container', 'image': R310,
        'image_build': 'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r310-gdn-barriers',
        'base': 'R310 = R304 (the R294b stack rebased onto stock vLLM XPU v0.29.0; public closure chains.r304 in '
                'repro/qwen38-27b-autoround-int4-b70/publication-manifest.json) plus the oneDNN r309 one-card fixed-K shapes and the '
                'vllm-xpu-kernels r310 GDN output fences. Python unchanged.',
        'previous_image_r304': package['runtime'].get('image'),
        'historical_image_ids': {k: v for k, v in package['runtime'].items() if k.endswith('_validated')},
    }
    package['project_patches'] = {'required': True, 'items': [
        'experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch',
        'packages/qwen38-27b-fp8-tp2-b70/overlays/b70_fa_verify_rows.py']}
    package['commands'] = {
        'preflight': f'docker pull {R310}',
        'launch': 'python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --model-dir /absolute/path/qwen3.8-27b-fp8 --state-dir /absolute/path/fp8-session',
        'health': 'python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py status --state-dir /absolute/path/fp8-session',
        'benchmark': 'BASE_URL=http://127.0.0.1:18124 OUT_DIR=/absolute/path/new-strict-attempt MODEL_NAME=qwen38-27b-fp8 repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh',
        'stop': 'python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py stop --state-dir /absolute/path/fp8-session'}
    deps = list(package['dependencies'])
    for item in NEW_DEPENDENCIES:
        if item not in deps:
            deps.append(item)
    if a.acceptance:
        for item in (str(a.acceptance.relative_to(ROOT)), str(a.acceptance.parent.relative_to(ROOT) / 'manifest.json')):
            if item not in deps:
                deps.append(item)
    package['dependencies'] = deps
    package['recommended_setup'] = {
        'cards': 2, 'mtp_depth': 5, 'draft_shortlist': '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt',
        'max_model_len': 33024, 'max_num_batched_tokens': 4096, 'max_num_seqs': 1, 'prefix_caching': False, 'image': R310,
        'launcher': 'packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py', 'acceptance_status': 'passed-on-configured-lab-host' if a.acceptance else 'pending-acceptance-replay',
        'clean_host_tested': False, 'evidence': 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md',
        'strict_pair_decode_tokens_s': pair, 'no_mtp_decode_tokens_s': no_mtp, 'depth1_decode_tokens_s': depth1,
        'previous_recipe': {'mtp_depth': 1, 'profile': 'depth-1', 'evidence': 'experiments/qwen38-27b-b70/data/2026-09-16-fp8-flagship/summary.json'}}
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
    print(f'manifest updated: featured {statistics.median(pair):.3f} tok/s from {pair}')


if __name__ == '__main__':
    main()
