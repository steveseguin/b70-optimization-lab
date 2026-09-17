#!/usr/bin/env python3
"""Move the one-card FP8 package manifest to the R311b single-checkpoint recipe (32,768-token profile) from receipts.

Reads the one-card 32K campaign receipts (data/2026-09-17-fp8-onecard-32k, copied by publish-fp8-review-receipts.py
--data) and the ckpt-3 research server at the same setting (data/2026-09-17-fp8-ckpt3/tp1-ckpt-32k-*), which together
are the two fresh servers. Rewrites the runtime, patches, recommended-profile fields, the three profiles' contexts and
the two recommended context charts; the no-MTP charts and the depth chart stay as measured on September 15-16.
"""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp1-b70/package.json'
CAMPAIGN = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-32k/'
CKPT3 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt3/'
R311B = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7'
R310 = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
SCOPE = ('One Intel Arc Pro B70, official Qwen3.8-27B-FP8, FP16 activations and KV, one user, prompt caching off, R311b image '
         '(single-checkpoint recurrent state) at the 32,768-token context with a 2,048-token prefill chunk, through the package '
         'launcher. Exact 2K/8K/16K-token inputs from unrepeated prose, code and documentation, 128-token continuations, two '
         'repeats; median within each of three content types, then across types (6 requests per point). Every continuation is '
         'identical to the no-MTP server. ')


def strict_median(path):
    return json.loads((ROOT / path).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def points(path, metric):
    by = json.loads((ROOT / path).read_text())['by_length']
    key = {'decode': 'decode_token_1_to_100_tps', 'prefill': 'server_prefill_tokens_per_s'}[metric]
    return [{'context_tokens': int(k), 'value': round(v[key], 3 if metric == 'decode' else 1), 'samples': v['samples']} for k, v in by.items()]


def main():
    results = json.loads((ROOT / CAMPAIGN / 'results.json').read_text())
    stage = results['tp1-pkg-32k']
    assert stage['strict']['exact'] == '12/12' and stage['strict_run2']['exact'] == '12/12' and stage['ladder']['verdict'] == 'exact' \
        and stage['context']['passed'] and stage['quality']['baseline_match_all'], stage
    pair = [strict_median(CKPT3 + 'tp1-ckpt-32k-strict-performance.json'), strict_median(CAMPAIGN + 'tp1-pkg-32k-strict-performance.json')]
    profiles = {}
    for name, key in (('max-context', 'tp1-pkg-max-context'), ('no-quantization', 'tp1-pkg-no-quantization')):
        s = results.get(key, {})
        ok = s.get('strict', {}).get('exact') == '12/12' and s.get('ladder', {}).get('verdict') == 'exact' and s.get('context', {}).get('passed')
        profiles[name] = (ok, s.get('strict', {}).get('tok_s_1_100'))
    package = json.loads(PACKAGE.read_text())
    lib = package['library']
    mc = f"{profiles['max-context'][1]:.1f}" if profiles['max-context'][0] else 'untested'
    nq = f"{profiles['no-quantization'][1]:.1f}" if profiles['no-quantization'][0] else 'untested'
    lib['summary'] = ('Official Qwen FP8 weights on one Intel Arc Pro B70. Recommended: MTP depth 5 with a draft-only INT4 shortlist '
                      f'head and a single-checkpoint recurrent state, 32,768 tokens of context, {statistics.median(pair):.1f} tok/s writing '
                      'speed; outputs identical to no MTP. A max-context profile reaches 40,960 tokens'
                      + (f' at {mc} tok/s' if mc != 'untested' else '') + f', and a no-quantization profile ({nq} tok/s, 28,672 tokens) '
                      'drafts with an FP16 copy of the output layer instead of an INT4 one.')
    lib['public_summary'] = lib['summary']
    lib['benchmark_status'] = (f'Strict 12-prompt suite on two fresh servers at the 32,768-token context: {pair[0]:.2f} / {pair[1]:.2f} tok/s, '
                               '12/12 identical to no MTP; 64-prompt sequential oracle plus queued passes 64/64; 2K/8K/16K prompts and a chat '
                               'quality suite match no MTP (September 17). The single-checkpoint recurrent state (R311b kernel + overlay) keeps '
                               'one GDN state block per request instead of six, raising the KV budget from 26,178 to 40,140 tokens at the same '
                               'memory setting and the same speed; its no-MTP reference at the resulting 896-token attention block is identical '
                               'to the 832-token one. Clean-host install and multiple users are untested.')
    lib['featured_metric'] = {
        'value': statistics.median(pair), 'unit': 'tok/s', 'label': 'Writing speed · MTP depth 5 · one card',
        'scope': (f'Median of two fresh R311b servers ({pair[0]:.3f} / {pair[1]:.3f}) at a 32,768-token context (2,048-token prefill chunk, '
                  'single-checkpoint recurrent state) on the fixed 12-prompt six-class suite, 512-token answers, class-balanced median of '
                  'tokens 1-100, cache zero, canaries passed, 12/12 complete outputs identical to no-MTP decoding, 64/64 on the sequential oracle.'),
        'evidence': CAMPAIGN + 'tp1-pkg-32k-strict-performance.json'}
    lib['tags'] = [t for t in lib['tags'] if t != '24K context'] + ['32K context']
    package['runtime'] = {'kind': 'container', 'image': R311B,
                          'image_build': 'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r311-gdn-checkpoint',
                          'base': 'R311b = R310 plus the vllm-xpu-kernels r311 single-checkpoint speculative GDN op (gdn_attention_ckpt); '
                                  'existing ops and Python unchanged.', 'previous_image_r310': R310}
    package['project_patches'] = {'required': True, 'items': [
        'experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_cpu_embed.py', 'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_verify_rows.py',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_draft_fp16_shortlist.py', 'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_gdn_checkpoint.py']}
    package['commands']['preflight'] = f'docker pull {R311B}'
    setup = package['recommended_setup']
    previous = {'max_model_len': setup['max_model_len'], 'max_num_batched_tokens': setup['max_num_batched_tokens'], 'image': setup['image'],
                'strict_pair_decode_tokens_s': setup['strict_pair_decode_tokens_s'], 'profiles': setup['profiles'],
                'evidence': 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'}
    setup.update(max_model_len=32768, max_num_batched_tokens=2048, image=R311B, single_checkpoint_state=True,
                 evidence='experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md', strict_pair_decode_tokens_s=pair,
                 previous_context=previous, kv_budget_tokens={'r310': 26178, 'r311b': 40140})
    setup['profiles'] = {'recommended': {'max_model_len': 32768, 'gpu_memory_utilization': 0.975, 'max_num_batched_tokens': 2048,
                                         'strict_pair_decode_tokens_s': pair}}
    for name, mml, mem, extra in (('max-context', 40960, 0.983, {}), ('no-quantization', 28672, 0.975, {'draft': 'fp16-shortlist'})):
        ok, rate = profiles[name]
        key = {'max-context': 'tp1-pkg-max-context', 'no-quantization': 'tp1-pkg-no-quantization'}[name]
        setup['profiles'][name] = dict(max_model_len=mml, gpu_memory_utilization=mem, max_num_batched_tokens=2048, **extra,
                                       strict_decode_tokens_s=rate, gates_exact=bool(ok), evidence=CAMPAIGN + f'{key}-strict-performance.json')
    package['missing'] = [m.replace('contexts above 30,720 tokens on one card', 'contexts above 40,960 tokens on one card') for m in package['missing']]
    for profile in package['performance_profiles']:
        if profile['id'] == 'decode-vs-context-recommended':
            profile.update(scope=SCOPE + 'Writing speed is tokens 1-100 after the first token.', evidence=CAMPAIGN + 'tp1-pkg-32k-context-summary.json',
                           points=points(CAMPAIGN + 'tp1-pkg-32k-context-summary.json', 'decode'))
        if profile['id'] == 'prefill-vs-context-recommended':
            profile.update(scope=SCOPE + 'Prompt reading is input tokens divided by server prefill time from the vLLM histogram.',
                           evidence=CAMPAIGN + 'tp1-pkg-32k-context-summary.json', points=points(CAMPAIGN + 'tp1-pkg-32k-context-summary.json', 'prefill'))
    deps = package['dependencies']
    for item in (CAMPAIGN + 'results.json', CAMPAIGN + 'tp1-pkg-32k-strict-performance.json', CAMPAIGN + 'tp1-pkg-32k-strict-vs-reference.json',
                 CAMPAIGN + 'tp1-pkg-32k-run2-strict-performance.json', CAMPAIGN + 'tp1-pkg-32k-context-summary.json',
                 CAMPAIGN + 'tp1-pkg-32k-ladder-vs-mtp0.json', CAMPAIGN + 'tp1-pkg-32k-quality.json', CAMPAIGN + 'tp1-pkg-32k-history-summary.json',
                 CAMPAIGN + 'tp1-pkg-max-context-strict-performance.json', CAMPAIGN + 'tp1-pkg-no-quantization-strict-performance.json',
                 CKPT3 + 'results.json', CKPT3 + 'tp1-ckpt-32k-strict-performance.json', CKPT3 + 'tp1-ckpt-mtp5-strict-performance.json',
                 CKPT3 + 'tp1-ckpt-mtp5-ladder-vs-mtp0.json', CKPT3 + 'tp1-ckpt-mtp5-quality.json', CKPT3 + 'tp1-ckpt-mtp5-context-summary.json',
                 CKPT3 + 'tp1-r311b-stock-strict-performance.json',
                 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/results.json',
                 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json',
                 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-stock-b896-strict-performance.json',
                 'experiments/qwen38-27b-b70/scripts/run-20260917-fp8-onecard-32k-campaign.py',
                 'experiments/qwen38-27b-b70/scripts/run-20260917-fp8-ckpt3-campaign.py',
                 'experiments/qwen38-27b-b70/scripts/run-20260917-fp8-ckpt2-campaign.py',
                 'experiments/qwen38-27b-b70/overlays/b70-gdn-checkpoint/b70_gdn_checkpoint.py',
                 'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch',
                 'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r311-gdn-checkpoint',
                 'experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r311-gdn-checkpoint.sh',
                 'experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md',
                 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'):
        if item not in deps:
            deps.append(item)
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
    print(f'one-card manifest updated: featured {statistics.median(pair):.3f} tok/s from {pair}; profiles {profiles}')


if __name__ == '__main__':
    main()
