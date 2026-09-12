#!/usr/bin/env python3
"""Native BF16 Transformers reference; run only under the exclusive device guard."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.streamers import BaseStreamer

ROOT = Path(__file__).resolve().parent
MODEL = Path('/mnt/raid-models/models/intake-20260912/openbmb--MiniCPM5-2B')
REVISION = '12a3808a956f869c767195e9266b59c4d21d92e2'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class TokenClock(BaseStreamer):
    def __init__(self):
        self.first = True
        self.timestamps = []
        self.ids = []
        self.start = time.perf_counter()

    def put(self, value):
        if self.first:
            self.first = False
            return
        ids = value.reshape(-1).tolist()
        assert len(ids) == 1, 'one token at a time, batch one only'
        torch.xpu.synchronize()
        self.timestamps.append(time.perf_counter() - self.start)
        self.ids.extend(ids)

    def end(self):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--smoke-only', action='store_true')
    parser.add_argument('--smoke-token-limit', type=int, default=256)
    parser.add_argument('--publisher-sampling', action='store_true')
    parser.add_argument('--system-prompt')
    parser.add_argument('--quality-only', action='store_true')
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError('Never overwrite an existing result')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((MODEL.parent / 'download-manifest.json').read_text())
    model_info = next(x for x in manifest['models'] if x['repo'] == 'openbmb/MiniCPM5-2B')
    assert model_info['revision'] == REVISION
    hashes = {}
    for entry in model_info['files']:
        path = MODEL / entry['name']
        assert path.stat().st_size == entry['size']
        actual = digest(path)
        assert actual == entry['verified_sha256'], entry['name']
        hashes[entry['name']] = actual
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    torch.manual_seed(7429)
    load_start = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, local_files_only=True, trust_remote_code=False,
        dtype=torch.bfloat16, attn_implementation='eager',
    ).eval().to('xpu:0')
    torch.xpu.synchronize()
    params = sum(p.numel() for p in model.parameters())
    assert params == 2516756480, params
    assert {p.dtype for p in model.parameters()} == {torch.bfloat16}
    assert {p.device.type for p in model.parameters()} == {'xpu'}
    assert model.config._attn_implementation == 'eager'
    sampling = {'do_sample': args.publisher_sampling,
                'temperature': 1.0 if args.publisher_sampling else None,
                'top_p': 0.95 if args.publisher_sampling else None,
                'top_k': 50 if args.publisher_sampling else None,
                'min_p': 0.0 if args.publisher_sampling else None}
    report = {
        'status': 'running', 'model': 'openbmb/MiniCPM5-2B', 'revision': REVISION,
        'model_hashes': hashes, 'parameter_count': params,
        'torch': torch.__version__, 'transformers': transformers.__version__,
        'transformers_source': '415e6d2f596ef2bd44fdee4261799200a7fc02bf',
        'transformers_install_origin': json.loads(importlib.metadata.distribution('transformers').read_text('direct_url.json')),
        'device': str(torch.xpu.get_device_properties(0)),
        'precision': 'native BF16 parameters and KV; no quantization',
        'attention': 'eager', 'compilation': 'none', 'draft': None,
        'tp': 1, 'concurrency': 1, 'enable_thinking': True,
        'load_seconds': time.perf_counter() - load_start,
        'threads': torch.get_num_threads(), 'rows': [],
        'generation_defaults': model.generation_config.to_dict(),
        'generation_mode': 'publisher-HF-sampling-seed7429' if args.publisher_sampling else 'greedy',
        'system_prompt': args.system_prompt,
        'generation_overrides': {**sampling, 'num_beams': 1, 'repetition_penalty': 1.0,
                                 'disable_compile': True, 'eos_token_id': [1, 130073],
                                 'pad_token_id': 1},
        'environment': {k: os.environ.get(k) for k in ['ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR',
                         'SYCL_DEVICE_FILTER', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']},
        'suite_hashes': {name: digest(ROOT / name) for name in
                         ['realistic-suite-v1.json', 'quality-canaries-v1.json']},
    }

    def save():
        temp = args.out.with_suffix('.tmp')
        temp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        temp.replace(args.out)

    def generate(prompt, identifier, suite, limit, use_cache=True, **metadata):
        torch.manual_seed(7429)
        messages = ([{'role': 'system', 'content': args.system_prompt}] if args.system_prompt else [])
        messages += [{'role': 'user', 'content': prompt}]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True,
            add_generation_prompt=True, enable_thinking=True,
            return_dict=True, return_tensors='pt',
        ).to('xpu:0')
        input_ids = inputs['input_ids'][0].tolist()
        assert input_ids[0] == model.config.bos_token_id
        torch.xpu.synchronize()
        clock = TokenClock()
        with torch.inference_mode():
            output = model.generate(
                **inputs, **sampling, num_beams=1,
                max_new_tokens=limit, use_cache=use_cache,
                repetition_penalty=1.0, streamer=clock,
                eos_token_id=[1, 130073], pad_token_id=1,
                return_dict_in_generate=True, disable_compile=True,
            )
        torch.xpu.synchronize()
        elapsed = time.perf_counter() - clock.start
        ids = output.sequences[0, len(input_ids):].tolist()
        kv_dtypes = []
        if use_cache:
            kv_dtypes = sorted({str(t.dtype) for layer in output.past_key_values.layers
                                for t in (layer.keys, layer.values)})
            assert kv_dtypes == ['torch.bfloat16'], kv_dtypes
        assert ids == clock.ids, 'stream timing must cover actual generated IDs exactly'
        raw = tokenizer.decode(ids, skip_special_tokens=False)
        text = tokenizer.decode(ids, skip_special_tokens=True)
        # Native thinking prompt already opens <think>; retain all reasoning in raw_text.
        final = text.split('</think>', 1)[1].strip() if '</think>' in text else ''
        row = {'id': identifier, 'suite': suite, 'prompt': prompt,
               'input_ids': input_ids, 'output_ids': ids, 'raw_text': raw,
               'decoded_text': text, 'final_text': final,
               'eos': bool(ids and ids[-1] in [1, 130073]),
               'generation_seconds': elapsed, 'token_timestamps_seconds': clock.timestamps,
               'cached_tokens': 0, 'cache_scope': 'fresh per generate call',
               'use_cache': use_cache, 'max_new_tokens': limit, **metadata}
        row['kv_dtypes_observed'] = kv_dtypes
        report['rows'].append(row)
        save()
        print(json.dumps({'id': identifier, 'suite': suite, 'tokens': len(ids),
                          'seconds': elapsed, 'eos': row['eos'],
                          'final_preview': final[:160]}, ensure_ascii=False), flush=True)
        return row

    save()
    if args.smoke_only:
        generate('Return only the number that equals 2 + 2.', 'smoke', 'smoke', args.smoke_token_limit)
    elif args.quality_only:
        for item in json.loads((ROOT / 'quality-canaries-v1.json').read_text())['prompts']:
            generate(item['prompt'], item['id'], 'quality', 2048)
    else:
        realistic = json.loads((ROOT / 'realistic-suite-v1.json').read_text())['prompts']
        quality = json.loads((ROOT / 'quality-canaries-v1.json').read_text())['prompts']
        # Unique realistic prompts first: no previous quality/diagnostic exposure.
        for item in realistic:
            generate(item['prompt'], item['id'], 'realistic', 512, **{'class': item['class']})
        for item in quality:
            generate(item['prompt'], item['id'], 'quality', 2048)
        # A separate completion-quality budget must not replace the 512-token timing rows.
        for item in realistic:
            original = next(r for r in report['rows'] if r['id'] == item['id'])
            if not original['eos']:
                longer = generate(item['prompt'], item['id'] + '-quality', 'realistic_quality',
                                  2048, quality_completion_of=item['id'],
                                  **{'class': item['class']})
                assert longer['output_ids'][:len(original['output_ids'])] == original['output_ids']
        for target in (2048, 8192):
            filler = 'This is an ordinary background record with no access key.\n'
            lead = 'Find the access key in the records below. Return only the key.\n'
            middle = '\nACCESS_KEY=K7B4-Z9P2\n'
            n = max(1, (target - 100) // len(tokenizer.encode(filler, add_special_tokens=False)))
            prompt = lead + filler * (n // 2) + middle + filler * (n - n // 2)
            prompt += '\nWhat is the access key? Return only the key.'
            generate(prompt, f'needle-{target}', 'context', 1024,
                     expected_final='K7B4-Z9P2', context_target=target)
        # Full repeated streams test state isolation after mixed prompt lengths.
        for row in list(report['rows']):
            if row['suite'] in ['quality', 'realistic', 'context']:
                generate(row['prompt'], row['id'] + '-repeat', 'repeat', row['max_new_tokens'],
                         repeat_of=row['id'])
        # This is an additional diagnostic, not a universal CPU/XPU oracle.
        for item in quality:
            generate(item['prompt'], item['id'] + '-no-cache', 'oracle', 8,
                     use_cache=False, oracle_of=item['id'])
        report['logit_diagnostics'] = []
        for item in quality:
            row = next(r for r in report['rows'] if r['id'] == item['id'])
            prompt_ids = row['input_ids']
            cache = None
            with torch.inference_mode():
                for step in range(min(8, len(row['output_ids']))):
                    prefix = prompt_ids + row['output_ids'][:step]
                    ids = torch.tensor([prefix], device='xpu:0')
                    incremental = model(
                        input_ids=ids if step == 0 else ids[:, -1:],
                        attention_mask=torch.ones_like(ids), past_key_values=cache,
                        use_cache=True, logits_to_keep=1,
                    )
                    cache = incremental.past_key_values
                    cached = incremental.logits[0, -1].float()
                    full = model(input_ids=ids, attention_mask=torch.ones_like(ids),
                                 use_cache=False, logits_to_keep=1).logits[0, -1].float()
                    top = torch.topk(cached, 2)
                    report['logit_diagnostics'].append({
                        'id': item['id'], 'step': step,
                        'cached_top1': int(cached.argmax()), 'full_top1': int(full.argmax()),
                        'generated_token': row['output_ids'][step],
                        'max_abs_error': float((cached - full).abs().max()),
                        'relative_l2': float(torch.linalg.vector_norm(cached-full) /
                                             torch.linalg.vector_norm(full)),
                        'cached_top1_top2_margin': float(top.values[0] - top.values[1]),
                    })
            del cache
            save()
    report['status'] = 'complete'
    report['peak_xpu_allocated_bytes'] = torch.xpu.max_memory_allocated()
    save()


if __name__ == '__main__':
    main()
