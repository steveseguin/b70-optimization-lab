#!/usr/bin/env python3
"""Complete the ONE-card FP8 LocalMaxxing queue payload: this host's hardware, the vLLM engine flags the typed API
expects (the generic builder is llama.cpp-oriented), and the exact launch identity. Idempotent; run after
build_rapid_realistic_localmaxxing_payload.py."""
import json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
Q = ROOT / 'experiments/qwen38-27b-b70/data/localmaxxing-qwen38-27b-fp8-tp1-mtp5-shortlist-r310-24k-strict-20260917.queue.json'
REV = ROOT / 'experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/'
queue = json.loads(Q.read_text())
entry = queue[0] if isinstance(queue, list) else queue['payloads'][0]
p = entry['payload']
first = json.loads((Path('/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-09-17-fp8-followup/tp1-ctx-24k-b2048-strict-performance.json')).read_text())['summary']
p['hardware'] = {'hwClass': 'DISCRETE_GPU', 'gpuName': 'Intel Arc Pro B70', 'gpuCount': 1, 'vramGb': 32,
                 'cpu': 'AMD EPYC 9015 8-Core Processor', 'ramGb': 16, 'os': 'Ubuntu 24.04.4 LTS'}
p['engineVersion'] = ('vLLM XPU v0.29.0 R310 image ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:'
                      'eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04')
p['backend'] = 'xpu'
p['tokSOut'] = statistics.median([first['class_balanced_tok_s_1_100_intervals_after_ttft']['median'], p['engineFlags']['tokSOutMedian']])
f = p['engineFlags']
f.update({
    'quantizationDetail': 'Official Qwen3.8-27B-FP8 (block-scaled FP8 weights, FP16 activations, FP16 KV) on one card; the 2.37 GiB input embedding is gathered in host memory (exact); the draft-only MTP head is an INT4 copy of 67,248 shortlisted output rows; every accepted token is verified by the unchanged FP8 target',
    'hostInputEmbedding': True, 'prefillChunkTokens': 2048,
    'apiMode': 'completions', 'apiKvCacheDtype': 'auto', 'kvCacheDtype': 'FP16', 'apiAttentionBackend': 'flash_attn',
    'attentionBackend': 'vLLM XPU FlashAttention v2 (decode-identical verifier rows above 1,536 keys)', 'flashAttn': True,
    'gpuLayers': -1, 'concurrency': 1, 'specDecoding': True, 'mtpEnabled': True, 'specMethod': 'qwen3_next_mtp',
    'specNumTokens': 5, 'targetModelVerifiedAcceptedTokens': True, 'tensorParallelSize': 1, 'maxRunningSeqs': 1,
    'max_model_len': '24576', 'max_num_batched_tokens': '2048', 'max_num_seqs': '1', 'gpu_memory_utilization': '0.975',
    'enable_xpu_graph': '0', 'draftShortlist': '/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt',
    'modelPath': '/mnt/fast-ai/llm-models/qwen3.8-27b-fp8',
    'commandSnippet': 'python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir /path/qwen3.8-27b-fp8 --state-dir /path/session  (ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04, one B70, host input embedding, MTP depth 5, 24,576 tokens)',
    'kernelBuild': 'vllm-xpu-kernels 0.1.14.1 + upstream GDN fix #544 + lab r310 GDN output fences; oneDNN 0e2a5bfe + r137a/r137b/r221/r309; stock vLLM XPU v0.29.0 + upstream fixes #53059/#51565/#53542 (R304 closure chains.r304)',
    'freshServerPair': [first['class_balanced_tok_s_1_100_intervals_after_ttft']['median'], f['tokSOutMedian']],
    'freshResponseValidity': ('Two fresh one-card MTP depth-5 servers (53.426 research probe, 53.435 shipped launcher) against the same-image '
                              'no-MTP server (19.406); full 12-prompt/six-class natural-512 suite over the completions API; every prompt sent once per '
                              'server; cached_tokens=0; canaries on every server; 12/12 complete token arrays identical to no-MTP on both servers; '
                              '64/64 on the 64-prompt sequential oracle plus queued passes; 2K/8K/16K context screen, chat quality suite and a 21-request logprob replay exact.'),
})
Q.write_text(json.dumps(queue, indent=1, ensure_ascii=False) + '\n')
print('payload completed: tokSOut', round(p['tokSOut'], 3))
