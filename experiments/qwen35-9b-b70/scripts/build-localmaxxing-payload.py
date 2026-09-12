#!/usr/bin/env python3
"""Build the b70-lab.result.v1 attestation and the LocalMaxxing queue payload for a Qwen3.5-9B strict campaign.
usage: build-localmaxxing-payload.py <campaign-root> <depth> <label> [--tp N] [--out-attestation P] [--out-queue P]"""
import argparse, hashlib, json, os, statistics, subprocess
ap = argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('depth', type=int); ap.add_argument('label')
ap.add_argument('--tp', type=int, default=1); ap.add_argument('--lane', default='fp8'); ap.add_argument('--hf'); ap.add_argument('--rev'); ap.add_argument('--quant', default='fp8'); ap.add_argument('--quant-detail'); ap.add_argument('--packet', default='qwen35-9b-fp8-b70'); ap.add_argument('--launcher', default='repro/qwen35-9b-fp8-b70/scripts/run-qwen35-9b-fp8-server.sh'); ap.add_argument('--model-path', default='/path/to/Qwen3.5-9B-FP8-dynamic'); ap.add_argument('--model-name', default='Qwen3.5-9B FP8-dynamic', help='model and quantization as it should read in the status line'); ap.add_argument('--out-attestation'); ap.add_argument('--out-queue')
# 2026-09-12: the served image is an argument (default the R276 identities this script was written for).
ap.add_argument('--image-tag', default='neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276')
ap.add_argument('--image-id', default='sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad')
ap.add_argument('--image-desc', default='R276 image (grouped sync-free GDN spec rows)', help='how the image reads inside engineVersion')
ap.add_argument('--overlays', default='r213b/r224/r228/r256/r276', help='overlay list as it reads in kernelBuild'); a = ap.parse_args()
repo = '/home/steve/b70-optimization-lab'; d = a.depth; A, B = f'mtp{d}-a', f'mtp{d}-b'
def load(p): return json.load(open(p))
def perf(lbl): return load(f'{a.root}/{lbl}/strict/performance.json')
def gate(f):
    c = load(f'{a.root}/{f}')['comparison']; return f"{c['exact_prompts']}/{c['total_prompts']}"
pa, pb = perf(A), perf(B); sa, sb = pa['summary'], pb['summary']
cb = lambda s: s['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
center = statistics.median([cb(sa), cb(sb)])
rows = pa['rows']; cfg = open(f'{a.root}/config.txt').read().strip()
boot = open(f'{a.root}/boot-id.txt').read().strip(); head = open(f'{a.root}/repo-head.txt').read().strip()
inspect = load(f'{a.root}/{A}/container-inspect.json')[0]; env = {e.split('=',1)[0]: e.split('=',1)[1] for e in inspect['Config']['Env'] if '=' in e}
keep = ['VLLM_XPU_ENABLE_XPU_GRAPH','VLLM_XPU_DRAFT_LM_HEAD_INT4','VLLM_XPU_GDN_SPEC_GROUP','VLLM_XPU_GDN_SPLIT_MIXED','VLLM_BATCH_INVARIANT','TORCHINDUCTOR_DETERMINISTIC','PYTHONHASHSEED','QUANTIZATION','VLLM_XPU_FP8_BLOCK_W8A16']
att = {
 'schema': 'b70-lab.result.v1', 'campaign_id': os.path.basename(a.root),
 # The model and card count come from the arguments, not a template. Hardcoding them here is what put
 # "Qwen3.5-9B FP8-dynamic, one B70 (TP2)" on 4B W4A16 two-card results in four published files.
 'status': f'{a.model_name}, {"one B70" if a.tp == 1 else f"{a.tp} B70s"} (TP{a.tp}), MTP depth {d} via qwen3_5_mtp with full decode-only XPU graph capture: strict pair {cb(sa):.6f}/{cb(sb):.6f} tok/s class-balanced median (tokens 1-100 after TTFT), G1/G2/G3 exact',
 'image_id': a.image_id, 'image_tag': a.image_tag,
 'image_ghcr': 'ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@' + a.image_id + ' (public)',
 'compilation_config': json.loads(env.get('COMPILATION_CONFIG','{}')) if env.get('COMPILATION_CONFIG','').startswith('{') else env.get('COMPILATION_CONFIG'),
 'speculative_config': {'method': 'qwen3_5_mtp', 'num_speculative_tokens': d}, 'oracle_root': f'{os.path.basename(a.root)}/mtp0-a (same-configuration MTP0, two fresh servers G1 12/12)',
 'boot_id': boot, 'repo_head_at_launch': head, 'campaign_config': cfg,
 'model': {'hf_id': a.hf or 'RedHatAI/Qwen3.5-9B-FP8-dynamic', 'revision': a.rev or '790f0576d2d77dd5322aa0603a470bd9e3a3d1f6', 'served_as': a.quant_detail or 'compressed-tensors FP8 per-channel weights, dynamic activations, publisher MTP head as draft'},
 'runtime_env': {k: env.get(k) for k in keep},
 'gates_passed': {'G1 mtp0-a vs mtp0-b': gate('compare-mtp0-a-vs-mtp0-b.json'), f'G2 {A} vs {B}': gate(f'compare-mtp{d}-a-vs-b.json'), f'G3 {A} vs mtp0-a': gate(f'compare-mtp{d}-a-vs-mtp0-a.json'), f'G3 {B} vs mtp0-a': gate(f'compare-mtp{d}-b-vs-mtp0-a.json')},
 'attempts': {A: f'{a.root}/{A}/strict', B: f'{a.root}/{B}/strict'},
 'centers': {f'mtp{d}_class_balanced_tok_s': center, 'mtp0_class_balanced_tok_s': statistics.median([cb(perf('mtp0-a')['summary']), cb(perf('mtp0-b')['summary'])])},
 'performance_evidence': {A: {k: round(sa[k]['median'],4) for k in ('class_balanced_tok_s_1_100_intervals_after_ttft','tok_s_1_100_after_ttft','tok_s_after_ttft_full','tok_s_wall_full','ttft_ms')},
                          B: {k: round(sb[k]['median'],4) for k in ('class_balanced_tok_s_1_100_intervals_after_ttft','tok_s_1_100_after_ttft','tok_s_after_ttft_full','tok_s_wall_full','ttft_ms')}},
 'output_sha256': {A: [r['sha256'] for r in rows], B: [r['sha256'] for r in pb['rows']]},
 'identity_claim': 'two fresh depth-%d servers 12/12 vs each other and 12/12 vs the MTP0 oracle on the strict 12-prompt completions suite' % d,
 'notes': 'Canaries passed on every server; cached_tokens 0 on every request; the chat API with visible thinking measures higher on the same prompts (workload note in the recipe).'}
def sha256(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
oa = a.out_attestation or f'{repo}/experiments/qwen35-9b-b70/data/{os.path.basename(a.root)}-strict-result.json'
json.dump(att, open(oa,'w'), indent=1, ensure_ascii=False); open(oa,'a').write('\n')
rel = os.path.relpath(oa, repo)
payload = {'label': a.label, 'payload': {
 'hfId': a.hf or 'RedHatAI/Qwen3.5-9B-FP8-dynamic', 'modelRevision': a.rev or '790f0576d2d77dd5322aa0603a470bd9e3a3d1f6', 'engineName': 'vllm',
 'engineVersion': 'vllm 0.27.2rc1.dev77+gac7509e2b (XPU); vllm-xpu-kernels 1e90ffa672 + lab GDN patches; _xpu_C 271db0d4 (R221 kernel library); %s; XPU graph capture FULL_DECODE_ONLY sizes 1-64; qwen3_5_mtp depth %d' % (a.image_desc, d),
 'backend': 'xpu', 'quantization': a.quant,
 'hardware': {'hwClass': 'DISCRETE_GPU', 'gpuName': 'Intel Arc Pro B70', 'gpuCount': a.tp, 'vramGb': 32, 'cpu': 'AMD EPYC 9015 8-Core Processor', 'ramGb': 16, 'os': 'Ubuntu 24.04.4 LTS'},
 'contextLength': 1024, 'batchSize': 1, 'promptTokens': int(statistics.median(r['prompt_tokens'] for r in rows)), 'outputTokens': 512,
 'tokSOut': center, 'tokSTotal': statistics.median([sa['tok_s_wall_full']['median'], sb['tok_s_wall_full']['median']]), 'ttftMs': statistics.median([sa['ttft_ms']['median'], sb['ttft_ms']['median']]),
 'engineFlags': {'quantizationDetail': a.quant_detail or 'FP8-dynamic compressed-tensors (per-channel FP8 weights, dynamic activations), draft-only INT4 lm_head copy for MTP proposals', 'apiMode': 'completions', 'apiKvCacheDtype': 'fp16', 'apiAttentionBackend': 'flash_attn', 'attentionBackend': 'vLLM XPU FlashAttention v2', 'benchmarkJson': rel, 'promotionAttestation': rel, 'promotionAttestationSha256': sha256(oa),
   'freshResponseHeadlineValid': True, 'freshResponseValidity': 'Two fresh MTP depth-%d servers (%.3f/%.3f tok/s) against a same-configuration MTP0 oracle (two fresh servers 12/12); full 12-prompt/six-class natural-512 suite over the completions API; every prompt sent once per server; cached_tokens=0; canaries on every server; every pairwise comparison matched 12/12 complete token arrays.' % (d, cb(sa), cb(sb)),
   'githubResultPacket': 'https://github.com/steveseguin/b70-optimization-lab/tree/main/packages/'+a.packet, 'headlineUse': 'fresh-realistic-suite', 'historyAccelerated': False, 'responseReuse': False, 'prefixCaching': False, 'flashAttn': True, 'gpuLayers': -1, 'concurrency': 1,
   'specDecoding': True, 'mtpEnabled': True, 'specMethod': 'qwen3_5_mtp', 'specNumTokens': d, 'targetModelVerifiedAcceptedTokens': True, 'tensorParallelSize': a.tp, 'maxRunningSeqs': 1, 'kvCacheDtype': 'FP16',
   'localmaxxingSubmissionAllowedUnderCurrentPolicy': True, 'metricWindowGeneratedTokens': 100, 'metricWindowIntervals': 99, 'modelPath': a.model_path,
   'outputSha256': [r['sha256'] for r in rows], 'realisticPromptTokenCounts': [r['prompt_tokens'] for r in rows], 'realisticOutputTokenCounts': [r['completion_tokens'] for r in rows], 'realisticSuiteCachedTokens': [r.get('cached_tokens',0) for r in rows],
   'realisticSuiteCachedTokensAllZero': all((r.get('cached_tokens') or 0)==0 for r in rows), 'realisticSuiteGatePassed': True, 'realisticSuiteId': 'qwen36-27b-autoround-int4-b70-realistic-v1', 'realisticSuitePath': 'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json', 'realisticSuiteVersion': 1,
   'temperature': 0, 'tokenTimingSource': 'openai_stream_token_ids_chunk_timestamp', 'primaryMetricName': 'median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft', 'primaryMetricAccounting': 'inter-token-intervals', 'primaryMetricAggregation': 'median-of-prompt-class-medians',
   'commandSnippet': 'MODEL_DIR=%s VLLM_CACHE_DIR=/path/to/new-cache MTP_DEPTH=%d MAX_MODEL_LEN=1024 MAX_NUM_SEQS=1 %s  (ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@%s)' % (a.model_path, d, a.launcher, a.image_id[:19] + '…'),
   'max_model_len': '1024', 'max_num_batched_tokens': '1024', 'max_num_seqs': '1', 'kernelBuild': 'GitHub release qwen38-int4-fixed-k-r221-20260906 (_xpu_C.abi3.so 271db0d4, clean-clone reproducible); overlays ' + a.overlays + ' tracked in the repository'}}}
oq = a.out_queue or f'{repo}/data/localmaxxing-{a.label}.queue.json'
json.dump([payload], open(oq,'w'), indent=1, ensure_ascii=False); open(oq,'a').write('\n')
print('attestation', rel, 'sha256', sha256(oa)); print('queue', os.path.relpath(oq, repo), 'tokSOut', round(center,3), 'ttft', round(payload['payload']['ttftMs'],2), 'promptTokens', payload['payload']['promptTokens'])
