#!/usr/bin/env python3
"""Move the one-card FP8 package manifest to the accepted R312d-c image (one-pass verifier attention) from receipts.

The numbers now come from the shipped-launcher acceptance campaign
(data/2026-09-18-fp8-onecard-r312d, copied from /mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918), which ran all
three profiles through packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py on the r312d-c image on September 18,
05:02-05:58 UTC and then restored the two-card service. The research-launcher run of the same image
(data/2026-09-18-fp8-lc4) stays in the manifest as the first fresh server. The long-prompt before/after table uses the
two R311b probes already in the repository (data/2026-09-17-fp8-probe1/tp1-pkg-max-context-summary.json, which is the
baseline the acceptance runner itself compared against, and data/2026-09-17-fp8-probe2/tp1-pkg-32k-context-summary.json,
the same profile on R311b; the two agree within 0.2%).

The image was pushed to ghcr on September 18, 2026 (publish-r312d-image-ghcr.sh, run by the user) as
ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918. The registry digest it came back with is the
same value as the local image id this manifest had already pinned, as it was for R311b on this containerd host, so
registry_pushed is true and the digest is verified rather than pending.

Idempotent: re-running on an already-R312d manifest keeps the R311b previous_context block.
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp1-b70/package.json'
ACC = 'experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/'
LC4 = 'experiments/qwen38-27b-b70/data/2026-09-18-fp8-lc4/'
PROBE1 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe1/'
PROBE2 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe2/'
CENSUS = 'experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/'
R312D = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a'
R311B = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7'
R310 = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
REGISTRY_TAG = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918'
DIGEST_NOTE = ('Verified after the push on 2026-09-18: the image was published to ghcr by the user '
               '(publish-r312d-image-ghcr.sh) and the registry digest came back equal to the local image id pinned '
               'here, as it did for R311b on this containerd host.')
LENGTHS = ('2048', '8192', '16384', '24576', '30720')
PROFILES = {'recommended': ('tp1-pkg-32k', 32768, 0.975), 'max-context': ('tp1-pkg-max-context', 40960, 0.983),
            'no-quantization': ('tp1-pkg-no-quantization', 28672, 0.975)}


def strict_median(path):
    return json.loads((ROOT / path).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def decode_by_length(path):
    by = json.loads((ROOT / path).read_text())['by_length']
    return {length: round(by[length]['decode_token_1_to_100_tps'], 2) for length in LENGTHS if length in by}


def change(candidate, baseline):
    return {length: round((candidate[length] / baseline[length] - 1) * 100, 1) for length in candidate}


def main():
    results = json.loads((ROOT / ACC / 'results.json').read_text())
    for profile, (stage_name, mml, _) in PROFILES.items():
        stage = results[stage_name]
        assert stage['profile'] == profile and stage['max_model_len'] == mml, stage
        assert stage['strict']['exact'] == '12/12' and stage['ladder']['verdict'] == 'exact' \
            and stage['context']['passed'] and stage['stop']['status'] == 'stopped', stage
    rec = results['tp1-pkg-32k']
    assert rec['strict_run2']['exact'] == '12/12' and rec['context_long']['passed'], rec
    assert rec['quality']['baseline_match_all'] and not rec['history']['divergent'] \
        and not rec['history']['logprob_divergent'], rec
    assert results['service']['strict']['exact'] == '12/12', results['service']

    pair = [strict_median(ACC + 'tp1-pkg-32k-strict-performance.json'),
            strict_median(ACC + 'tp1-pkg-32k-run2-strict-performance.json')]
    research_pair = [strict_median(LC4 + 'tp1-r312c-multiq-strict-performance.json'),
                     strict_median(LC4 + 'tp1-r312c-multiq-run2-strict-performance.json')]
    candidate = decode_by_length(ACC + 'tp1-pkg-32k-long-context-summary.json')
    r311b_max = decode_by_length(PROBE1 + 'tp1-pkg-max-context-summary.json')
    r311b_32k = decode_by_length(PROBE2 + 'tp1-pkg-32k-context-summary.json')
    change_32k = change(candidate, r311b_32k)
    change_max = change(candidate, r311b_max)

    package = json.loads(PACKAGE.read_text())
    lib = package['library']
    lib['summary'] = (
        'Official Qwen FP8 weights on one Intel Arc Pro B70. Recommended: MTP depth 5 with a draft-only INT4 shortlist '
        'head and a single-checkpoint recurrent state, 32,768 tokens of context, '
        f'{statistics.median(pair):.1f} tok/s writing speed; outputs identical to no MTP. A max-context profile reaches '
        f'40,960 tokens at {results["tp1-pkg-max-context"]["strict"]["tok_s_1_100"]:.1f} tok/s, and a no-quantization '
        f'profile ({results["tp1-pkg-no-quantization"]["strict"]["tok_s_1_100"]:.1f} tok/s, 28,672 tokens) drafts with '
        'an FP16 copy of the output layer instead of an INT4 one. Since September 18 the image also computes the draft '
        'verifier\'s attention rows in one pass, which leaves short prompts as they were and writes 9-17% faster after '
        'prompts above 16,384 tokens.')
    lib['public_summary'] = lib['summary']
    lib['tags'] = list(dict.fromkeys(lib['tags']))
    lib['benchmark_status'] = (
        f'Accepted through the shipped launcher on the R312d-c image (September 18, 05:02-05:58 UTC). Strict 12-prompt '
        f'suite on a fresh 32,768-token server, twice: {pair[0]:.2f} / {pair[1]:.2f} tok/s, 12/12 identical to no MTP '
        f'each time; 64-prompt sequential oracle plus two queued passes 64/64; the 2K/8K/16K screen, the '
        f'2,048-30,720-token long corpus in three content types, a chat quality suite and a 21-request logprob replay '
        f'all exact against the same R311b no-MTP references. The other two profiles passed the same strict, ladder and '
        f'context gates on this image: max-context (40,960) '
        f'{results["tp1-pkg-max-context"]["strict"]["tok_s_1_100"]:.2f} tok/s, no-quantization (28,672) '
        f'{results["tp1-pkg-no-quantization"]["strict"]["tok_s_1_100"]:.2f} tok/s. The single-checkpoint recurrent state '
        f'(R311b kernel + overlay) keeps one GDN state block per request instead of six, raising the KV budget from '
        f'26,178 to 40,140 tokens at the same memory setting. The one-pass verifier attention (R312d-c) leaves every '
        f'output unchanged and raises writing speed after a long prompt by {change_max["16384"]:.0f}% at 16K, '
        f'{change_max["24576"]:.0f}% at 24K and {change_max["30720"]:.0f}% at 30K. The image is published to ghcr as '
        f'r312d-fp8-tp1-20260918 and its registry digest matches the pinned value. Clean-host install and multiple '
        f'users are untested.')
    lib['featured_metric'] = {
        'value': statistics.median(pair), 'unit': 'tok/s',
        'label': 'Writing speed · MTP depth 5 · one card',
        'scope': f'Median of two strict runs on a fresh R312d-c package-launcher server ({pair[0]:.3f} / {pair[1]:.3f}) at '
                 f'a 32,768-token context (2,048-token prefill chunk, single-checkpoint recurrent state, one-pass verifier '
                 f'attention) on the fixed 12-prompt six-class suite, 512-token answers, class-balanced median of tokens '
                 f'1-100, cache zero, canaries passed, 12/12 complete outputs identical to no-MTP decoding on both runs, '
                 f'64/64 on the sequential oracle. The research launcher measured {research_pair[0]:.3f} / '
                 f'{research_pair[1]:.3f} on its own fresh server of the same image.',
        'evidence': ACC + 'tp1-pkg-32k-strict-performance.json'}
    package['runtime'] = {
        'kind': 'container', 'image': R312D,
        'image_digest_status': DIGEST_NOTE, 'registry_tag': REGISTRY_TAG, 'registry_pushed': True,
        'image_build': 'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-multiq',
        'base': 'R312d-c = R311b with _xpu_C and the GDN device library rebuilt for the r312 one-pass verifier attention op '
                'paged_decode_multiq (Dockerfile.r312c-multiq), then its libattn_multiq_kernels_xe_2.so rebuilt with DPC++ '
                '2026.0.0 / IGC 2.34.4 / ocloc 26.18 against the sycl-tla revision 87f6850 that vllm-xpu-kernels 0.1.14.1 pins '
                'as CUTLASS_REVISION (Dockerfile.r312d-multiq). The upstream flash-attention library is the untouched upstream '
                'binary. Census against it: 22/22 bit-exact, max abs 0.0, at v-tile 64 and 256.',
        'toolchain_rule': 'Every _xpu_C or GDN rebuild must use the CUTLASS_REVISION the kernel CMakeLists.txt pins (87f6850 for '
                          'vllm-xpu-kernels 0.1.14.1). Building against the clean-clone recipe\'s cd76379 changed the attention '
                          'output by 7.6e-6 and failed the census (2026-09-18).',
        'previous_image_r311b': R311B, 'previous_image_r310': R310}
    package['project_patches'] = {'required': True, 'items': [
        'experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch',
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-paged-decode-multiq-r312-20260917.patch',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_cpu_embed.py',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_verify_rows.py',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_multiq.py',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_draft_fp16_shortlist.py',
        'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_gdn_checkpoint.py']}
    package['commands']['preflight'] = f'docker pull {R312D}'

    setup = package['recommended_setup']
    if setup.get('image') != R312D:
        setup['previous_context'] = {
            'max_model_len': setup['max_model_len'], 'max_num_batched_tokens': setup['max_num_batched_tokens'],
            'image': setup['image'], 'strict_pair_decode_tokens_s': setup['strict_pair_decode_tokens_s'],
            'profiles': setup['profiles'],
            'evidence': 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'}
    setup.update(image=R312D, registry_tag=REGISTRY_TAG, image_digest_status=DIGEST_NOTE, registry_pushed=True,
                 one_pass_verifier_attention=True, previous_image_r311b=R311B,
                 acceptance_status='passed-on-configured-lab-host',
                 acceptance_campaign='experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py',
                 acceptance_evidence=ACC + 'results.json',
                 acceptance_window_utc='2026-09-18T05:02Z/2026-09-18T05:58Z',
                 strict_pair_decode_tokens_s=pair,
                 research_server_strict_pair_decode_tokens_s=research_pair,
                 research_server_evidence=LC4 + 'results.json')
    setup.pop('r312d_strict_pair_decode_tokens_s', None)
    setup.pop('r312d_evidence', None)
    setup['profiles'] = {}
    for profile, (stage_name, mml, mem) in PROFILES.items():
        entry = {'max_model_len': mml, 'gpu_memory_utilization': mem, 'max_num_batched_tokens': 2048,
                 'gates_exact': True, 'gates_exact_on_image': 'r312d-c',
                 'evidence': ACC + f'{stage_name}-strict-performance.json'}
        if profile == 'recommended':
            entry['strict_pair_decode_tokens_s'] = pair
            entry['research_server_strict_pair_decode_tokens_s'] = research_pair
        else:
            entry['strict_decode_tokens_s'] = strict_median(ACC + f'{stage_name}-strict-performance.json')
        if profile == 'no-quantization':
            entry['draft'] = 'fp16-shortlist'
        setup['profiles'][profile] = entry
    setup['long_prompt_decode_tokens_s'] = {
        'scope': 'Writing speed for tokens 1-100 after prompts of 2,048-30,720 tokens from the unrepeated 2026-09-17 long '
                 'corpus (code, documentation and prose; median within each content type, then across types; two repeats, '
                 '6 requests per point), measured through the package launcher on the accepted image. Every continuation is '
                 'identical to the no-MTP reference on both images.',
        'r311b_recommended_32768': r311b_32k, 'r311b_max_context_40960': r311b_max,
        'r312d_c_recommended_32768': candidate,
        'change_percent_vs_r311b_recommended': change_32k,
        'change_percent_vs_r311b_max_context': change_max,
        'evidence': {'r312d_c': ACC + 'tp1-pkg-32k-long-context-summary.json',
                     'r311b_recommended': PROBE2 + 'tp1-pkg-32k-context-summary.json',
                     'r311b_max_context': PROBE1 + 'tp1-pkg-max-context-summary.json'}}

    deps = package['dependencies']
    for item in ([ACC + name for name in (
                     'README.md', 'results.json', 'campaign.log',
                     'tp1-pkg-32k-strict-performance.json', 'tp1-pkg-32k-strict-vs-reference.json',
                     'tp1-pkg-32k-run2-strict-performance.json', 'tp1-pkg-32k-run2-strict-vs-reference.json',
                     'tp1-pkg-32k-ladder-vs-mtp0.json', 'tp1-pkg-32k-context-summary.json',
                     'tp1-pkg-32k-long-context-summary.json', 'tp1-pkg-32k-quality.json',
                     'tp1-pkg-32k-history-summary.json', 'tp1-pkg-32k-launch.json', 'tp1-pkg-32k-state.json',
                     'tp1-pkg-max-context-strict-performance.json', 'tp1-pkg-max-context-strict-vs-reference.json',
                     'tp1-pkg-max-context-ladder-vs-mtp0.json', 'tp1-pkg-max-context-context-summary.json',
                     'tp1-pkg-max-context-launch.json', 'tp1-pkg-max-context-state.json',
                     'tp1-pkg-no-quantization-strict-performance.json',
                     'tp1-pkg-no-quantization-strict-vs-reference.json',
                     'tp1-pkg-no-quantization-ladder-vs-mtp0.json', 'tp1-pkg-no-quantization-context-summary.json',
                     'tp1-pkg-no-quantization-launch.json', 'tp1-pkg-no-quantization-state.json')]
                 + [LC4 + name for name in (
                     'results.json', 'campaign.log',
                     'tp1-r312c-multiq-strict-performance.json', 'tp1-r312c-multiq-strict-vs-reference.json',
                     'tp1-r312c-multiq-run2-strict-performance.json', 'tp1-r312c-multiq-run2-strict-vs-reference.json',
                     'tp1-r312c-multiq-ladder-vs-mtp0.json', 'tp1-r312c-multiq-context-summary.json',
                     'tp1-r312c-multiq-long-context-summary.json', 'tp1-r312c-multiq-quality.json',
                     'tp1-r312c-multiq-history-summary.json', 'tp1-r312c-multiq-launch.json',
                     'tp1-r312c-multiq-state.json')]
                 + [PROBE1 + 'tp1-pkg-max-context-summary.json', PROBE2 + 'tp1-pkg-32k-context-summary.json',
                    CENSUS + 'README.md',
                    'experiments/qwen38-27b-b70/scripts/run-20260918-fp8-lc3-campaign.py',
                    'experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py',
                    'experiments/qwen38-27b-b70/overlays/b70-fa-multiq/b70_fa_multiq.py',
                    'packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_multiq.py',
                    'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-paged-decode-multiq-r312-20260917.patch',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312c-multiq',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-multiq',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-builder-a',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r312d-builder-b',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312c-multiq.sh',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312d-multiq-toolchain.sh',
                    'experiments/qwen38-27b-b70/docker/rebase-v0290/publish-r312d-image-ghcr.sh',
                    'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md']):
        if item not in deps and (ROOT / item).exists():
            deps.append(item)
    missing = [item for item in deps if not (ROOT / item).exists()]
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
    print(f'one-card manifest accepted on R312d-c: strict {pair[0]:.3f} / {pair[1]:.3f} tok/s through the launcher, '
          f'max-context {setup["profiles"]["max-context"]["strict_decode_tokens_s"]:.3f}, '
          f'no-quantization {setup["profiles"]["no-quantization"]["strict_decode_tokens_s"]:.3f}; '
          f'long-prompt change vs R311b max-context {change_max}')
    if missing:
        print('WARNING: dependencies that do not resolve: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
