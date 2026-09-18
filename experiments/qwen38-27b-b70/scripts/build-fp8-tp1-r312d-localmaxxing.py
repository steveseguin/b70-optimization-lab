#!/usr/bin/env python3
"""Derive the LocalMaxxing attestation and queue payload for the one-card FP8 R312d-c recipe (one-pass verifier
attention, 32,768 tokens, 2026-09-18) from the R311b 32K ones: same model, gates and suite; the image, pair and every
evidence hash come from the two fresh r312d-c servers -- lc-4 (research launcher) and the shipped-launcher acceptance
campaign. The record it supersedes is cmu5wc2e50804lq01r0br2i5p (54.325, R311b, 32,768).

This only writes the payload. It does not submit: the r312d-c image is not pushed to ghcr yet, and submission is a
separate, explicit step (see docs/localmaxxing.md). Idempotent.
"""
import datetime
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'experiments/qwen38-27b-b70/data'
OLD_ATT = D / '2026-09-17-fp8-tp1-mtp5-r311b-32k-promotion-attestation.json'
OLD_Q = D / 'localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r311b-32k-strict-20260917.queue.json'
NEW_ATT = D / '2026-09-18-fp8-tp1-mtp5-r312d-32k-promotion-attestation.json'
NEW_Q = D / 'localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r312d-32k-strict-20260918.queue.json'
ACC = 'experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/'
LC4 = 'experiments/qwen38-27b-b70/data/2026-09-18-fp8-lc4/'
CKPT2 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/'
LABEL = 'qwen38-27b-fp8-tp1-mtp5-shortlist-r312d-32k-strict'
SUPERSEDES = 'cmu5wc2e50804lq01r0br2i5p'
R311B_SHA = '7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7'
R312D_SHA = 'ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a'
R312D = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:' + R312D_SHA
IDENTITY = ('qwen38-27b-fp8-tp1-r312d-c-cpu-embed-mtp5-int4-shortlist67k-fa-multiq-verify-rows-gdn-checkpoint-'
            '32768-batched2048-mem0975-seqs1-nocache')


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def summary_of(rel):
    return json.loads((ROOT / rel).read_text())['summary']


def median_of(rel):
    return summary_of(rel)['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def main():
    acc = json.loads((ROOT / ACC / 'results.json').read_text())
    lc4 = json.loads((ROOT / LC4 / 'results.json').read_text())
    pkg = acc['tp1-pkg-32k']
    assert pkg['strict']['exact'] == '12/12' and pkg['strict_run2']['exact'] == '12/12' \
        and pkg['ladder']['verdict'] == 'exact' and pkg['context']['passed'] and pkg['context_long']['passed'] \
        and pkg['quality']['baseline_match_all'] and not pkg['history']['divergent'] \
        and not pkg['history']['logprob_divergent'], pkg
    research = lc4['tp1-r312c-multiq']
    assert research['strict']['exact'] == '12/12' and research['ladder']['verdict'] == 'exact', research

    first = median_of(LC4 + 'tp1-r312c-multiq-strict-performance.json')
    second = median_of(ACC + 'tp1-pkg-32k-strict-performance.json')
    repeat = median_of(ACC + 'tp1-pkg-32k-run2-strict-performance.json')
    oracle = median_of(CKPT2 + 'tp1-mtp0-b896-strict-performance.json')
    pair = [first, second]
    value = statistics.median(pair)

    att = json.loads(OLD_ATT.read_text())
    att['created_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    att['profile_id'] = 'qwen38-27b-fp8-tp1-mtp5-shortlist-r312d-32768'
    att['supersedes_record_id'] = SUPERSEDES
    att['submission_status'] = ('queued, not submitted: the r312d-c image is not pushed to ghcr yet '
                                '(experiments/qwen38-27b-b70/docker/rebase-v0290/publish-r312d-image-ghcr.sh, run by '
                                'the repository owner). Submitting is a separate explicit step.')
    att['headline'].update(
        value=value, candidate_values=pair, matched_oracle_value=oracle, gain_percent=100 * (value / oracle - 1),
        note=('Official Qwen3.8-27B-FP8 on ONE B70 (32 GiB), R312d-c image: host-memory input embedding, MTP depth 5 '
              'with the draft-only INT4 shortlist head, the single-checkpoint recurrent state (one GDN state block per '
              'request, replay-commit of the accepted prefix) and the one-pass verifier attention (the draft\'s 2-6 '
              'rows computed in a single pass over the cache instead of one pass each), 32,768-token context at 0.975 '
              'memory. The first server is the September 18 lc-4 campaign (research launcher); the second is the '
              f'September 18 acceptance campaign through the package launcher, which also repeated the suite on the '
              f'same server at {repeat:.3f}. Both servers are 12/12 identical to the same-image no-MTP server at the '
              '896-token attention block (itself 12/12 identical to the 832-token no-MTP reference); the package '
              'server is also 64/64 on the 64-prompt sequential oracle plus two queued passes, exact on the 2K/8K/16K '
              'context screen, the 2,048-30,720-token long corpus in three content types, the chat quality suite and '
              'the 21-request logprob replay, and stopped cleanly. Outputs are byte-identical to the R311b record this '
              f'supersedes ({SUPERSEDES}); the change is speed after long prompts (+9.9% at 16K, +14.5% at 24K, '
              '+17.3% at 30K) at the same short-prompt headline.'))
    att['performance_evidence'] = {'path': ACC + 'tp1-pkg-32k-strict-performance.json',
                                   'sha256': sha(ACC + 'tp1-pkg-32k-strict-performance.json')}
    att['performance_receipts'] = {
        'first_server_performance_path': LC4 + 'tp1-r312c-multiq-strict-performance.json',
        'first_server_performance_sha256': sha(LC4 + 'tp1-r312c-multiq-strict-performance.json'),
        'second_server_repeat_performance_path': ACC + 'tp1-pkg-32k-run2-strict-performance.json',
        'second_server_repeat_performance_sha256': sha(ACC + 'tp1-pkg-32k-run2-strict-performance.json'),
        'oracle_performance_path': CKPT2 + 'tp1-mtp0-b896-strict-performance.json',
        'oracle_performance_sha256': sha(CKPT2 + 'tp1-mtp0-b896-strict-performance.json')}
    att['identity']['runtime_revision'] = 'vLLM XPU v0.29.0 R312d-c image ' + R312D
    att['identity']['optimization_identity'] = IDENTITY
    att['identity']['launcher_sha256'] = sha('packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py')
    att['identity']['overlay_sha256'] = sha('packages/qwen38-27b-fp8-tp1-b70/overlays/b70_gdn_checkpoint.py')
    att['identity']['multiq_overlay_sha256'] = sha('packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_multiq.py')
    att['identity']['kernel_patch_sha256'] = sha(
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch')
    att['identity']['multiq_kernel_patch_sha256'] = sha(
        'experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-paged-decode-multiq-r312-20260917.patch')
    gates = list(att['gates'].keys())
    att['quality_evidence'] = [{'path': p, 'sha256': sha(p), 'supports': list(s)} for p, s in (
        (ACC + 'results.json', gates),
        (ACC + 'tp1-pkg-32k-strict-vs-reference.json',
         ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed', 'target_model_unchanged', 'no_quality_loss']),
        (ACC + 'tp1-pkg-32k-run2-strict-vs-reference.json', ['deterministic_repeats_passed', 'fresh_server_repeat_passed']),
        (ACC + 'tp1-pkg-32k-ladder-vs-mtp0.json',
         ['exact_or_target_oracle_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
        (ACC + 'tp1-pkg-32k-context-summary.json', ['exact_or_target_oracle_passed', 'deterministic_repeats_passed']),
        (ACC + 'tp1-pkg-32k-long-context-summary.json',
         ['exact_or_target_oracle_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
        (ACC + 'tp1-pkg-32k-quality.json',
         ['varied_task_quality_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
        (ACC + 'tp1-pkg-32k-history-summary.json',
         ['deterministic_repeats_passed', 'target_model_unchanged', 'no_quality_loss']),
        (LC4 + 'results.json', gates),
        (LC4 + 'tp1-r312c-multiq-strict-vs-reference.json',
         ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed']),
        (CKPT2 + 'tp1-mtp0-b896-strict-vs-reference.json', ['target_model_unchanged', 'no_quality_loss']))]
    NEW_ATT.write_text(json.dumps(att, indent=1) + '\n')

    queue = json.loads(OLD_Q.read_text())
    entry = queue[0] if isinstance(queue, list) else queue['payloads'][0]
    entry['label'] = LABEL
    p = entry['payload']
    perf = json.loads((ROOT / ACC / 'tp1-pkg-32k-strict-performance.json').read_text())
    summary = perf['summary']
    p['engineVersion'] = 'vLLM XPU v0.29.0 R312d-c image ' + R312D
    p['contextLength'] = 32768
    p['tokSOut'] = value
    p['tokSTotal'] = summary['tok_s_wall_full']['median']
    p['ttftMs'] = summary['ttft_ms']['median']
    p['notes'] = ('Official Qwen3.8-27B-FP8 (FP16 activations and KV) on ONE Intel Arc Pro B70: the 2.37 GiB input '
                  'embedding lives in host memory, native MTP depth 5 with a draft-only INT4 shortlist head, a '
                  'single-checkpoint recurrent state (one GDN state block per request instead of six) and the '
                  'verifier\'s draft rows computed in one pass over the KV cache, 32,768-token context; every accepted '
                  'token verified by the unchanged FP8 target; 12/12 outputs identical to no-MTP decoding, 64/64 on '
                  'the 64-prompt sequential oracle, the 2,048-30,720-token long corpus and the logprob replay '
                  f'identical; second of two fresh servers, through the package launcher. Supersedes {SUPERSEDES} '
                  '(same outputs, 10-17% faster after prompts above 16K).')
    f = p['engineFlags']
    f['attentionBackend'] = ('vLLM XPU FlashAttention v2 (decode-identical verifier rows; one pass over the cache for '
                             'all draft rows above 4,096 keys)')
    f['benchmarkJson'] = ACC + 'tp1-pkg-32k-strict-performance.json'
    f['freshResponseValidity'] = (
        f'Two fresh one-card MTP depth-5 servers on the r312d-c image ({first:.3f} research launcher, {second:.3f} '
        f'shipped package launcher) against the same-image no-MTP server ({oracle:.3f}); full 12-prompt/six-class '
        f'natural-512 suite over the completions API; every prompt sent once per server; cached_tokens=0; canaries on '
        f'every server; 12/12 complete token arrays identical to no-MTP on both servers, and again on the package '
        f'server\'s repeat ({repeat:.3f}); 64/64 on the 64-prompt sequential oracle plus queued passes; 2K/8K/16K '
        f'context screen, the 2,048-30,720-token long corpus, chat quality suite and a 21-request logprob replay '
        f'exact.')
    f['outputSha256'] = perf['output_sha256s']
    f['promptSha256'] = perf['prompt_sha256s']
    f['realisticSuiteCachedTokens'] = perf['realistic_final_gate']['cached_tokens']
    f['realisticSuiteCachedTokensAllZero'] = perf['realistic_final_gate']['cached_tokens_all_zero']
    f['tokSOutMedian'] = second
    f['tokSOutP10'] = summary['tok_s_1_100_intervals_after_ttft']['p10']
    f['tokSOutMean'] = summary['tok_s_1_100_intervals_after_ttft']['mean']
    f['tokSOutStdev'] = summary['tok_s_1_100_intervals_after_ttft']['stdev']
    f['tokSFullAfterTtftMedian'] = summary['tok_s_after_ttft_full']['median']
    f['tokSFullAfterTtftP10'] = summary['tok_s_after_ttft_full']['p10']
    f['tokSFullAfterTtftMean'] = summary['tok_s_after_ttft_full']['mean']
    f['tokSTotalWallMedian'] = summary['tok_s_wall_full']['median']
    f['tokSTotalWallP10'] = summary['tok_s_wall_full']['p10']
    f['tokSTotalWallMean'] = summary['tok_s_wall_full']['mean']
    f['ttftMsMedian'] = summary['ttft_ms']['median']
    f['ttftMsP10'] = summary['ttft_ms']['p10']
    f['ttftMsMean'] = summary['ttft_ms']['mean']
    f['max_model_len'] = '32768'
    f['freshServerPair'] = pair
    f['kernelBuild'] = ('vllm-xpu-kernels 0.1.14.1 + upstream GDN fix #544 + lab r310 GDN output fences + r311 '
                        'single-checkpoint GDN state + r312 paged_decode_multiq, the last built against the pinned '
                        'CUTLASS_REVISION 87f6850 with DPC++ 2026.0.0 / IGC 2.34.4 / ocloc 26.18 (r312d-c); oneDNN '
                        '0e2a5bfe + r137a/r137b/r221/r309; stock vLLM XPU v0.29.0 + upstream fixes '
                        '#53059/#51565/#53542 (R304 closure chains.r304)')
    f['singleCheckpointRecurrentState'] = True
    f['onePassVerifierAttention'] = True
    f['onePassVerifierAttentionMinKeys'] = 4096
    f['supersedesRecordId'] = SUPERSEDES
    f['submissionStatus'] = att['submission_status']
    f['optimizationIdentity'] = IDENTITY
    f['promotionAttestation'] = str(NEW_ATT.relative_to(ROOT))
    f['promotionAttestationSha256'] = sha(str(NEW_ATT.relative_to(ROOT)))
    f['promotionIdentity'] = att['identity']
    for key in list(f):
        if isinstance(f[key], str):
            f[key] = f[key].replace(R311B_SHA, R312D_SHA)
            if key == 'commandSnippet':
                f[key] = f[key].replace('R311b', 'R312d-c')
    NEW_Q.write_text(json.dumps(queue, indent=1) + '\n')
    print(f'attestation {NEW_ATT.name}: {value:.3f} tok/s from {pair} (oracle {oracle:.3f}); queue {NEW_Q.name}; '
          f'supersedes {SUPERSEDES}; NOT submitted')


if __name__ == '__main__':
    main()
