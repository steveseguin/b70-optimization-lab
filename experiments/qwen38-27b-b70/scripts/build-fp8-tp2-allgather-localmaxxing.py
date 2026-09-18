#!/usr/bin/env python3
"""Derive the LocalMaxxing attestation and queue payload for the two-card FP8 allgather-allreduce recipe (2026-09-17)
from the R310 ring-allreduce ones: same identity, image and gates; the pair becomes the comm-2 fresh server and the
allgather acceptance replay; every evidence hash is recomputed from the repository files. Idempotent."""
import datetime
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'experiments/qwen38-27b-b70/data'
OLD_ATT = D / '2026-09-17-fp8-tp2-mtp5-r310-promotion-attestation.json'
OLD_Q = D / 'localmaxxing-qwen38-27b-fp8-tp2-mtp5-shortlist-r310-strict-20260917.queue.json'
NEW_ATT = D / '2026-09-17-fp8-tp2-mtp5-r310-allgather-promotion-attestation.json'
NEW_Q = D / 'localmaxxing-qwen38-27b-fp8-tp2-mtp5-shortlist-allgather-r310-strict-20260917.queue.json'
COMM2 = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-comm2/'
PACKET = 'experiments/qwen38-27b-b70/data/2026-09-17-fp8-two-card-allgather/'
LABEL = 'qwen38-27b-fp8-tp2-mtp5-shortlist-allgather-r310-strict'


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def median_of(rel):
    return json.loads((ROOT / rel).read_text())['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']['median']


def main():
    first = median_of(COMM2 + 'tp2-ag-mtp5-strict-performance.json')
    second = median_of(PACKET + 'acceptance-performance.json')
    oracle = median_of(COMM2 + 'tp2-ag-mtp0-strict-performance.json')
    summary = json.loads((ROOT / PACKET / 'summary.json').read_text())
    assert summary['passed'] and summary['strict']['no_mtp_reference_exact'] == 12
    commit = summary['public_source_commit']
    pair = [first, second]
    value = statistics.median(pair)

    att = json.loads(OLD_ATT.read_text())
    att['created_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    att['profile_id'] = 'qwen38-27b-fp8-tp2-mtp5-shortlist-allgather-r310-33024'
    att['headline'].update(value=value, candidate_values=pair, matched_oracle_value=oracle, gain_percent=100 * (value / oracle - 1),
                           note=('Official Qwen3.8-27B-FP8 on two B70s, MTP depth 5 with the draft-only INT4 shortlist head, decode-identical '
                                 'verifier rows and the two-rank allreduce done as one allgather plus a fixed-order add (R310 image, '
                                 'launcher overlay). The first server is the September 17 comm-2 campaign (tp2-ag-mtp5); the second is the '
                                 f'package launcher replayed from an anonymous public-source download at commit {commit}. Both are 12/12 '
                                 'identical to the same-image no-MTP server on the strict suite; the first is also 64/64 on the 64-prompt '
                                 'sequential oracle plus two queued passes and exact on the 2K/8K/16K context screen and the chat quality '
                                 'suite; the no-MTP server under the same overlay reproduced the ring-allreduce outputs 12/12; the replay adds '
                                 'six practical requests with exact repeats and an owned clean stop.'))
    att['performance_evidence'] = {'path': PACKET + 'acceptance-performance.json', 'sha256': sha(PACKET + 'acceptance-performance.json')}
    att['performance_receipts'] = {
        'first_server_performance_path': COMM2 + 'tp2-ag-mtp5-strict-performance.json',
        'first_server_performance_sha256': sha(COMM2 + 'tp2-ag-mtp5-strict-performance.json'),
        'oracle_performance_path': COMM2 + 'tp2-ag-mtp0-strict-performance.json',
        'oracle_performance_sha256': sha(COMM2 + 'tp2-ag-mtp0-strict-performance.json'),
        'acceptance_manifest': PACKET + 'manifest.json', 'acceptance_manifest_sha256': sha(PACKET + 'manifest.json')}
    att['identity']['optimization_identity'] = 'qwen38-27b-fp8-tp2-r310-mtp5-int4-shortlist67k-fa-verify-rows-allgather-allreduce-33024-batched4096-seqs1-nocache'
    att['identity']['launcher_sha256'] = sha('packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py')
    att['identity']['overlay_sha256'] = sha('packages/qwen38-27b-fp8-tp2-b70/overlays/b70_allgather_allreduce.py')
    quality = []
    for path, supports in ((PACKET + 'summary.json', att['gates'].keys()), (PACKET + 'acceptance-strict-comparison.json',
                            ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed', 'target_model_unchanged', 'no_quality_loss']),
                           (COMM2 + 'results.json', att['gates'].keys()),
                           (COMM2 + 'tp2-ag-mtp5-ladder-vs-mtp0.json', ['exact_or_target_oracle_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
                           (COMM2 + 'tp2-ag-mtp5-context-summary.json', ['exact_or_target_oracle_passed', 'deterministic_repeats_passed']),
                           (COMM2 + 'tp2-ag-mtp5-quality.json', ['varied_task_quality_passed', 'deterministic_repeats_passed', 'no_quality_loss']),
                           (COMM2 + 'tp2-ag-mtp5-strict-vs-reference.json', ['exact_or_target_oracle_passed', 'fresh_server_repeat_passed']),
                           (COMM2 + 'tp2-ag-mtp0-strict-vs-reference.json', ['target_model_unchanged', 'no_quality_loss'])):
        quality.append({'path': path, 'sha256': sha(path), 'supports': list(supports)})
    att['quality_evidence'] = quality
    NEW_ATT.write_text(json.dumps(att, indent=1) + '\n')

    queue = json.loads(OLD_Q.read_text())
    entry = queue[0] if isinstance(queue, list) else queue['payloads'][0]
    entry['label'] = LABEL
    p = entry['payload']
    perf = json.loads((ROOT / PACKET / 'acceptance-performance.json').read_text())['summary']
    p['tokSOut'] = value
    for key, src in (('tokSTotal', 'class_balanced_full_completion_tok_s_wall'), ('ttftMs', 'ttft_ms')):
        if src in perf:
            p[key] = perf[src]['median'] if isinstance(perf[src], dict) else perf[src]
    p['notes'] = ('Official Qwen3.8-27B-FP8 (FP16 activations and KV) on two Intel Arc Pro B70, vLLM XPU R310, native MTP depth 5 with a '
                  'draft-only INT4 shortlist head; the two-rank allreduce is one allgather plus a fixed-order add (bit-identical to the ring '
                  'allreduce); every accepted token verified by the unchanged FP8 target; 12/12 outputs identical to no-MTP decoding, 64/64 '
                  'on the 64-prompt sequential oracle; second of two fresh servers, replayed from an anonymous public-source download.')
    f = p['engineFlags']
    f['tokSOutMedian'] = second
    f['allgatherAllreduce'] = True
    f['optimizationIdentity'] = att['identity']['optimization_identity']
    f['promotionAttestation'] = str(NEW_ATT.relative_to(ROOT))
    f['promotionAttestationSha256'] = sha(str(NEW_ATT.relative_to(ROOT)))
    f['promotionIdentity'] = att['identity']
    f['commandSnippet'] = f.get('commandSnippet', '').replace('MTP depth 5, 33,024 tokens', 'MTP depth 5, allgather allreduce overlay, 33,024 tokens')
    for key in list(f):
        if isinstance(f[key], str) and 'promotion-attestation' in f[key]:
            f[key] = f[key].replace('2026-09-17-fp8-tp2-mtp5-r310-promotion-attestation.json', NEW_ATT.name)
        if isinstance(f[key], str) and '2026-09-17-fp8-two-card-depth5' in f[key]:
            f[key] = f[key].replace('2026-09-17-fp8-two-card-depth5', '2026-09-17-fp8-two-card-allgather')
    for key in list(entry):
        if isinstance(entry[key], str) and '2026-09-17-fp8-tp2-mtp5-r310-promotion-attestation' in entry[key]:
            entry[key] = entry[key].replace('2026-09-17-fp8-tp2-mtp5-r310-promotion-attestation.json', NEW_ATT.name)
    NEW_Q.write_text(json.dumps(queue, indent=1) + '\n')
    print(f'attestation {NEW_ATT.name}: {value:.3f} tok/s from {pair} (oracle {oracle:.3f}); queue {NEW_Q.name}')


if __name__ == '__main__':
    main()
