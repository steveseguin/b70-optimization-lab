#!/usr/bin/env bash
# Close the exact-serial-GDN MTP1 line's evidence after A367 (record suite) lands:
# file the suite result and identity, build the promotion attestation from the certified data
# files, build the LocalMaxxing payload queue, and print the submit command. No hand-typed numbers.
set -Eeuo pipefail
repo=/home/steve/llm-optimizations
E=$repo/experiments/qwen38-flash-next-fp8-b70; D=$E/data; T=$E/tools
B=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70
run=$(ls -d "$B"/*attempt367 | grep -v -E 'failed|frozen|supervisor' | head -1)
[[ -f "$run/realistic-suite-v1-result.json" ]] || { echo "A367 suite result missing in $run"; exit 1; }
cp "$run/realistic-suite-v1-result.json" "$D/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json"
cp "$run/identity.txt" "$D/20260913-tp4-mtp1-a367-native-exact-gdn-identity.txt"
python3 - <<'PY'
import json; j=json.load(open('/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json'))
s=j['summary']['class_balanced_tok_s_1_100_intervals_after_ttft']; print('A367 class-balanced median', s['median'])
print('cached tokens', [r.get('cached_tokens') for r in j.get('rows', j.get('results', []))][:12])
g=j.get('realistic_final_gate', {}); print('final gate', {k:v for k,v in g.items() if isinstance(v,bool)})
PY
cd "$repo"
python3 "$T/build-q38-flash-next-promotion-attestation.py" \
  --bench experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json \
  --out experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json \
  --profile-id qwen38-flash-next-fp8-tp4-mtp1-fullgraphdet-4352-placement-hctriton-qsafused-exactgdn-realistic-v1 \
  --runtime-revision 6d8724577dabbee5fa0bbc70c4d927c6174c8d8a \
  --optimization-identity tp4-ep4-fullgraphdet-mtp1-4352-ple-embed-budget12p25-uva-coldexperts-hostplaced-3p5gib-w13n32-mkldnndet-oneccl-twoshots-hctriton-qsafused-exactgdn-stage-bbae3c5 \
  --headline-note "deterministic full-decode-graph line with one publisher MTP token on the certified fused-QSA overlay 6d872457, with the GDN verifier rows run by the kernel extension's own exact serial mode (VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1, persistent scratch, completion barrier) on stage v2: the served 2f829747 stage with _xpu_C rebuilt from kernel head bbae3c5 over e421889 (ad25aa9 generalises the exact replay to two rows; the served build gates it to four). vLLM overlay, MoE kernel, tuned map, UVA offload, expert placement and collective runtime unchanged. SAME OUTPUT AUTHORITY as the 37.83 tok/s line: exact-2K afffd211 and exact-4K 1d833e5f on the certification servers A364, A365, A366 and the record server; kernel-level probe bit-identical; quality byte for byte against the certified battery (7/7 exact cases, 16/16 repeats one hash, exact needle); twelve cold suite rows with cached_tokens 0" \
  --evidence "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json:varied_task_quality_passed,exact_or_target_oracle_passed,deterministic_repeats_passed,target_model_unchanged,no_quality_loss" \
  --evidence "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json:varied_task_quality_passed,exact_or_target_oracle_passed,deterministic_repeats_passed,fresh_server_repeat_passed,target_model_unchanged,no_quality_loss" \
  --evidence "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json:fresh_server_repeat_passed,deterministic_repeats_passed,exact_or_target_oracle_passed"
python3 "$T/build-q38-headroom-localmaxxing-payload.py" \
  --result experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json \
  --identity experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-identity.txt \
  --attestation experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json \
  --label qwen38-flash-next-official-fp8-tp4-fullgraphdet-mtp1-placement-hctriton-qsafused-exactgdn-realistic-20260913 \
  --engine-version 6d8724577dabbee5fa0bbc70c4d927c6174c8d8a \
  --optimization-identity tp4-ep4-fullgraphdet-mtp1-4352-ple-embed-budget12p25-uva-coldexperts-hostplaced-3p5gib-w13n32-mkldnndet-oneccl-twoshots-hctriton-qsafused-exactgdn-stage-bbae3c5 \
  --notes "Same identity as the approved 37.825654 tok/s lossless-MTP1 line (vLLM overlay 6d872457, TP4/EP4 deterministic full-decode graph, one speculative token, never-routed experts host-placed, both reference Triton kernels), with the GDN verifier rows run by the kernel extension's exact serial mode on a rebuilt _xpu_C (kernel head bbae3c5 over e421889). Outputs identical to that line at 2K and 4K on four servers; quality profile byte for byte; fixed cold 12-prompt realistic suite sent once, cached_tokens 0 on every row." \
  --out experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-localmaxxing-payload-queue.json
python3 -c "
import json; q=json.load(open('experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-localmaxxing-payload-queue.json'))[0]
print('payload label', q['label']); print('tokSOut', q['payload']['tokSOut'], 'attestation', q['payload']['engineFlags']['promotionAttestation'])"
echo "submit with: python3 scripts/submit_localmaxxing_results.py --payloads experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-localmaxxing-payload-queue.json --label qwen38-flash-next-official-fp8-tp4-fullgraphdet-mtp1-placement-hctriton-qsafused-exactgdn-realistic-20260913"
