#!/usr/bin/env python3
"""Move the one-card FP8 package manifest from the R311b image to R312d-c (one-pass verifier attention) from receipts.

Reads the lc-4 receipts (data/2026-09-18-fp8-lc4, copied from /mnt/fast-ai/bench-results/fp8-lc4-20260918) for the
candidate's own gates, and the two R311b long-prompt probes already in the repository
(data/2026-09-17-fp8-probe1/tp1-pkg-max-context-summary.json, data/2026-09-17-fp8-probe2/tp1-pkg-32k-context-summary.json)
for the before/after writing-speed table. Rewrites the runtime, the patch and overlay lists, the preflight command, the
recommended-profile block and the dependency list; the context and depth charts stay exactly as measured on the R311b
image, because lc-4 ran through the research launcher and the shipped-launcher acceptance campaign
(run-20260918-fp8-onecard-r312d-campaign.py) has not run yet.

The image is pinned by its LOCAL id: ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918 has not
been pushed yet (publish-r312d-image-ghcr.sh, run by the user). On this containerd host the registry digest is the same
value as the local image id, as it was for R311b; the manifest says so and the digest is re-checked after the push.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/qwen38-27b-fp8-tp1-b70/package.json'
LC4 = 'experiments/qwen38-27b-b70/data/2026-09-18-fp8-lc4/'
PROBE1 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe1/'
PROBE2 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe2/'
CENSUS = 'experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/'
R312D = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a'
R311B = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7'
R310 = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04'
REGISTRY_TAG = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918'
DIGEST_NOTE = ('Pinned by the local image id; the image is not pushed yet (publish-r312d-image-ghcr.sh, run by the user). '
               'On this containerd host the registry digest equals the local image id, as it did for R311b, and it is '
               're-verified against this value after the push.')
LENGTHS = ('2048', '8192', '16384', '24576', '30720')


def strict_median(path):
    return json.loads((ROOT / path).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def decode_by_length(path):
    by = json.loads((ROOT / path).read_text())['by_length']
    return {length: round(by[length]['decode_token_1_to_100_tps'], 2) for length in LENGTHS if length in by}


def main():
    results = json.loads((ROOT / LC4 / 'results.json').read_text())
    stage = results['tp1-r312c-multiq']
    assert stage['strict']['exact'] == '12/12' and stage['strict_run2']['exact'] == '12/12', stage['strict']
    assert stage['ladder']['verdict'] == 'exact' and stage['context']['passed'] and stage['context_long']['passed'], stage
    assert stage['quality']['baseline_match_all'] and not stage['history']['divergent'] \
        and not stage['history']['logprob_divergent'], stage
    pair = [strict_median(LC4 + 'tp1-r312c-multiq-strict-performance.json'),
            strict_median(LC4 + 'tp1-r312c-multiq-run2-strict-performance.json')]
    candidate = decode_by_length(LC4 + 'tp1-r312c-multiq-long-context-summary.json')
    r311b_max = decode_by_length(PROBE1 + 'tp1-pkg-max-context-summary.json')
    r311b_32k = decode_by_length(PROBE2 + 'tp1-pkg-32k-context-summary.json')
    change = {length: round((candidate[length] / r311b_32k[length] - 1) * 100, 1) for length in candidate}

    package = json.loads(PACKAGE.read_text())
    lib = package['library']
    lib['summary'] = (lib['summary'].split(' Since September 18')[0]
                      + ' Since September 18 the image also computes the draft verifier\'s attention rows in one pass, '
                        'which leaves short prompts as they were and writes 9-17% faster after prompts above 16,384 tokens.')
    lib['public_summary'] = lib['summary']
    lib['benchmark_status'] = (
        'Strict 12-prompt suite on two fresh R311b servers at the 32,768-token context: 54.36 / 54.29 tok/s, 12/12 identical '
        'to no MTP; 64-prompt sequential oracle plus queued passes 64/64; 2K/8K/16K prompts and a chat quality suite match no '
        'MTP (September 17). The single-checkpoint recurrent state (R311b kernel + overlay) keeps one GDN state block per '
        'request instead of six, raising the KV budget from 26,178 to 40,140 tokens at the same memory setting and the same '
        f'speed. On September 18 the package moved to the R312d-c image, which computes the verifier\'s 2-6 attention rows in '
        f'one pass (paged_decode_multiq): on a fresh research server every gate was exact against the same R311b no-MTP '
        f'references -- strict twice ({pair[0]:.2f} / {pair[1]:.2f} tok/s, 12/12 each), the 64-prompt ladder 64/64 three times, '
        f'the 2K/8K/16K screen, the 2,048-30,720-token long corpus in three content types, the chat quality suite and the '
        f'21-request logprob replay -- and the writing speed after long prompts rose by '
        f'{change["16384"]:.0f}% at 16K, {change["24576"]:.0f}% at 24K and {change["30720"]:.0f}% at 30K. The shipped-launcher '
        'acceptance campaign on all three profiles is pending, as is the registry push. Clean-host install and multiple users '
        'are untested.')
    package['runtime'] = {
        'kind': 'container', 'image': R312D,
        'image_digest_status': DIGEST_NOTE, 'registry_tag': REGISTRY_TAG, 'registry_pushed': False,
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
    previous = {'max_model_len': setup['max_model_len'], 'max_num_batched_tokens': setup['max_num_batched_tokens'],
                'image': setup['image'], 'strict_pair_decode_tokens_s': setup['strict_pair_decode_tokens_s'],
                'profiles': setup['profiles'],
                'evidence': 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'}
    setup.update(image=R312D, registry_tag=REGISTRY_TAG, image_digest_status=DIGEST_NOTE,
                 one_pass_verifier_attention=True, previous_image_r311b=R311B,
                 acceptance_status='staged-pending-acceptance-campaign',
                 acceptance_campaign='experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py',
                 r312d_strict_pair_decode_tokens_s=pair,
                 r312d_evidence=LC4 + 'results.json', previous_context=previous)
    setup['long_prompt_decode_tokens_s'] = {
        'scope': 'Writing speed for tokens 1-100 after prompts of 2,048-30,720 tokens from the unrepeated 2026-09-17 long '
                 'corpus (code, documentation and prose; median within each content type, then across types; two repeats, '
                 '6 requests per point). Every continuation is identical to the no-MTP reference on both images.',
        'r311b_recommended_32768': r311b_32k, 'r311b_max_context_40960': r311b_max,
        'r312d_c_recommended_32768': candidate, 'change_percent_vs_r311b_recommended': change,
        'evidence': {'r312d_c': LC4 + 'tp1-r312c-multiq-long-context-summary.json',
                     'r311b_recommended': PROBE2 + 'tp1-pkg-32k-context-summary.json',
                     'r311b_max_context': PROBE1 + 'tp1-pkg-max-context-summary.json'}}
    for name in ('max-context', 'no-quantization'):
        setup['profiles'][name]['gates_exact_on_image'] = 'r311b'
        setup['profiles'][name]['pending_on_r312d'] = True
    setup['profiles']['recommended']['r312d_strict_pair_decode_tokens_s'] = pair
    setup['profiles']['recommended']['r312d_gates_exact'] = True
    setup['profiles']['recommended']['r312d_evidence'] = LC4 + 'results.json'

    deps = package['dependencies']
    for item in (LC4 + 'results.json', LC4 + 'campaign.log',
                 LC4 + 'tp1-r312c-multiq-strict-performance.json', LC4 + 'tp1-r312c-multiq-strict-vs-reference.json',
                 LC4 + 'tp1-r312c-multiq-run2-strict-performance.json', LC4 + 'tp1-r312c-multiq-run2-strict-vs-reference.json',
                 LC4 + 'tp1-r312c-multiq-ladder-vs-mtp0.json', LC4 + 'tp1-r312c-multiq-context-summary.json',
                 LC4 + 'tp1-r312c-multiq-long-context-summary.json', LC4 + 'tp1-r312c-multiq-quality.json',
                 LC4 + 'tp1-r312c-multiq-history-summary.json', LC4 + 'tp1-r312c-multiq-launch.json',
                 LC4 + 'tp1-r312c-multiq-state.json',
                 PROBE1 + 'tp1-pkg-max-context-summary.json', PROBE2 + 'tp1-pkg-32k-context-summary.json',
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
                 'experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md'):
        if item not in deps and (ROOT / item).exists():
            deps.append(item)
    missing = [item for item in deps if not (ROOT / item).exists()]
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + '\n')
    print(f'one-card manifest moved to R312d-c: strict {pair[0]:.3f} / {pair[1]:.3f} tok/s, long-prompt change {change}')
    if missing:
        print('WARNING: dependencies that do not resolve: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
