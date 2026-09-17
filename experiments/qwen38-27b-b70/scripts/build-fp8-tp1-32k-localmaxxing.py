#!/usr/bin/env python3
"""Derive the LocalMaxxing attestation and queue payload for the one-card FP8 R311b single-checkpoint recipe
(32,768 tokens, 2026-09-17) from the R310 24K ones: same model, gates and suite; the image, context, pair and every
evidence hash come from the ckpt-3 research server and the one-card 32K package campaign. Idempotent."""
import datetime
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'experiments/qwen38-27b-b70/data'
OLD_ATT = D / '2026-09-17-fp8-tp1-mtp5-r310-24k-promotion-attestation.json'
OLD_Q = D / 'localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r310-24k-strict-20260917.queue.json'
NEW_ATT = D / '2026-09-17-fp8-tp1-mtp5-r311b-32k-promotion-attestation.json'
NEW_Q = D / 'localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r311b-32k-strict-20260917.queue.json'
PKG = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-32k/'
CKPT3 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt3/'
CKPT2 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/'
LABEL = 'qwen38-27b-fp8-tp1-mtp5-shortlist-r311b-32k-strict'
R311B = 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7'


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def median_of(rel):
    return json.loads((ROOT / rel).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def main():
    first = median_of(CKPT3 + 'tp1-ckpt-32k-strict-performance.json')
    second = median_of(PKG + 'tp1-pkg-32k-strict-performance.json')
    oracle = median_of(CKPT2 + 'tp1-mtp0-b896-strict-performance.json')
    results = json.loads((ROOT / PKG / 'results.json').read_text())['tp1-pkg-32k']
    assert results['strict']['exact'] == '12/12' and results['strict_run2']['exact'] == '12/12' and results['ladder']['verdict'] == 'exact' \
        and results['context']['passed'] and results['quality']['baseline_match_all'] and not results['history']['divergent'] \
        and not results['history']['logprob_divergent'], results
    pair = [first, second]
    value = statistics.median(pair)
    att = json.loads(OLD_ATT.read_text())
    att['created_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    att['profile_id'] = 'qwen38-27b-fp8-tp1-mtp5-shortlist-r311b-32768'
    att['headline'].update(value=value, candidate_values=pair, matched_oracle_value=oracle, gain_percent=100 * (value / oracle - 1),
                           note=('Official Qwen3.8-27B-FP8 on ONE B70 (32 GiB), R311b image: host-memory input embedding, MTP depth 5 with '
                                 'the draft-only INT4 shortlist head, decode-identical verifier rows and the single-checkpoint recurrent '
                                 'state (one GDN state block per request, replay-commit of the accepted prefix), 32,768-token context at '
                                 '0.975 memory. The first server is the September 17 ckpt-3 campaign at 32,768 (research launcher); the '
                                 'second is the package launcher (tp1-pkg-32k). Both are 12/12 identical to the same-image no-MTP server '
                                 'at the 896-token attention block (itself 12/12 identical to the 832-token no-MTP reference); the package '
                                 'server is also 64/64 on the 64-prompt sequential oracle plus two queued passes, exact on the 2K/8K/16K '
                                 'context screen, the chat quality suite and the 21-request logprob replay, and stopped cleanly.'))
    att['performance_evidence'] = {'path': PKG + 'tp1-pkg-32k-strict-performance.json', 'sha256': sha(PKG + 'tp1-pkg-32k-strict-performance.json')}
    att['performance_receipts'] = {
        'first_server_performance_path': CKPT3 + 'tp1-ckpt-32k-strict-performance.json',
        'first_server_performance_sha256': sha(CKPT3 + 'tp1-ckpt-32k-strict-performance.json'),
        'oracle_performance_path': CKPT2 + 'tp1-mtp0-b896-strict-performance.json',
        'oracle_performance_sha256': sha(CKPT2 + 'tp1-mtp0-b896-strict-performance.json')}
    att['identity']['runtime_revision'] = 'vLLM XPU v0.29.0 R311b image ' + R311B
    att['identity']['optimization_identity'] = 'qwen38-27b-fp8-tp1-r311b-cpu-embed-mtp5-int4-shortlist67k-fa-verify-rows-gdn-checkpoint-32768-batched2048-mem0975-seqs1-nocache'
    att['identity']['launcher_sha256'] = sha('packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py')
    att['identity']['overlay_sha256'] = sha('packages/qwen38-27b-fp8-tp1-b70/overlays/b70_gdn_checkpoint.py')
    att['identity']['kernel_patch_sha256'] = sha('experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch')
    gates = list(att['gates'].keys())
    att['quality_evidence'] = [{'path': p, 'sha256': sha(p), 'supports': list(s)} for p, s in (
        (PKG + 'results.json', gates),
        (PKG + 'tp1-pkg-32k-strict-vs-reference.json', ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed', 'target_model_unchanged', 'no_quality_loss']),
        (PKG + 'tp1-pkg-32k-run2-strict-vs-reference.json', ['deterministic_repeats_passed', 'fresh_server_repeat_passed']),
        (PKG + 'tp1-pkg-32k-ladder-vs-mtp0.json', ['exact_or_target_oracle_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
        (PKG + 'tp1-pkg-32k-context-summary.json', ['exact_or_target_oracle_passed', 'deterministic_repeats_passed']),
        (PKG + 'tp1-pkg-32k-quality.json', ['varied_task_quality_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
        (PKG + 'tp1-pkg-32k-history-summary.json', ['deterministic_repeats_passed', 'target_model_unchanged', 'no_quality_loss']),
        (CKPT3 + 'results.json', gates),
        (CKPT3 + 'tp1-ckpt-32k-strict-vs-reference.json', ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed']),
        (CKPT2 + 'tp1-mtp0-b896-strict-vs-reference.json', ['target_model_unchanged', 'no_quality_loss']))]
    NEW_ATT.write_text(json.dumps(att, indent=1) + '\n')

    queue = json.loads(OLD_Q.read_text())
    entry = queue[0] if isinstance(queue, list) else queue['payloads'][0]
    entry['label'] = LABEL
    p = entry['payload']
    perf = json.loads((ROOT / PKG / 'tp1-pkg-32k-strict-performance.json').read_text())['summary']
    p['engineVersion'] = 'vLLM XPU v0.29.0 R311b image ' + R311B
    p['contextLength'] = 32768
    p['tokSOut'] = value
    for key, src in (('tokSTotal', 'class_balanced_full_completion_tok_s_wall'), ('ttftMs', 'ttft_ms')):
        if src in perf:
            p[key] = perf[src]['median'] if isinstance(perf[src], dict) else perf[src]
    p['notes'] = ('Official Qwen3.8-27B-FP8 (FP16 activations and KV) on ONE Intel Arc Pro B70: the 2.37 GiB input embedding lives in host '
                  'memory, native MTP depth 5 with a draft-only INT4 shortlist head, decode-identical verifier rows and a single-checkpoint '
                  'recurrent state (one GDN state block per request instead of six), 32,768-token context; every accepted token verified by '
                  'the unchanged FP8 target; 12/12 outputs identical to no-MTP decoding, 64/64 on the 64-prompt sequential oracle, logprob '
                  'replay identical; second of two fresh servers, through the package launcher.')
    f = p['engineFlags']
    f['tokSOutMedian'] = second
    f['max_model_len'] = '32768'
    f['singleCheckpointRecurrentState'] = True
    f['optimizationIdentity'] = att['identity']['optimization_identity']
    f['promotionAttestation'] = str(NEW_ATT.relative_to(ROOT))
    f['promotionAttestationSha256'] = sha(str(NEW_ATT.relative_to(ROOT)))
    f['promotionIdentity'] = att['identity']
    for key in list(f):
        if isinstance(f[key], str):
            f[key] = f[key].replace('eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04', '7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7')
            f[key] = f[key].replace('24,576 tokens', '32,768 tokens').replace('R310', 'R311b') if key == 'commandSnippet' else f[key]
    NEW_Q.write_text(json.dumps(queue, indent=1) + '\n')
    print(f'attestation {NEW_ATT.name}: {value:.3f} tok/s from {pair} (oracle {oracle:.3f}); queue {NEW_Q.name}')


if __name__ == '__main__':
    main()
