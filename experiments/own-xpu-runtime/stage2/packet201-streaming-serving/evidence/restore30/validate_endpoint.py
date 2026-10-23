#!/usr/bin/env python3
"""Validate an OpenAI-compatible local endpoint: correctness, determinism, prompt caching, MTP, speed, optional vision.

Usage: validate_endpoint.py --base http://127.0.0.1:18130 --model NAME --kind vllm|llamacpp [--vision]
Exit 0 only if every required check passes. Writes a JSON receipt next to this script.
"""
import argparse, base64, json, re, struct, time, urllib.request, zlib
from pathlib import Path


def post(base, path, body, timeout=900):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r), time.time() - t


def get(base, path, timeout=30):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return r.read().decode()


def chat(a, content, max_tokens, extra=None):
    body = {'model': a.model, 'messages': [{'role': 'user', 'content': content}], 'max_tokens': max_tokens,
            'temperature': 0, 'top_p': 1, 'seed': 7, 'chat_template_kwargs': {'enable_thinking': False}}
    if a.kind == 'llamacpp':
        body['cache_prompt'] = True
    body.update(extra or {})
    return post(a.base, '/v1/chat/completions', body)


def stream_ttft(a, content, max_tokens):
    body = {'model': a.model, 'messages': [{'role': 'user', 'content': content}], 'max_tokens': max_tokens,
            'temperature': 0, 'seed': 7, 'stream': True, 'chat_template_kwargs': {'enable_thinking': False}}
    if a.kind == 'llamacpp':
        body['cache_prompt'] = True
    req = urllib.request.Request(a.base + '/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t = time.time(); first = None; text = []
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith('data:') or line == 'data: [DONE]':
                continue
            d = json.loads(line[5:])
            for ch in d.get('choices', []):
                piece = (ch.get('delta') or {}).get('content')
                if piece:
                    if first is None:
                        first = time.time() - t
                    text.append(piece)
    return first, ''.join(text), time.time() - t


def png(w=64, h=64):
    raw = b''.join(b'\x00' + b''.join((b'\x00\x00\xff' if (x > 44 and y < 20) else b'\xff\x00\x00') for x in range(w)) for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def mtp_counters(a):
    if a.kind != 'vllm':
        return None
    m = get(a.base, '/metrics')
    out = {}
    for key in ('vllm:spec_decode_num_draft_tokens_total', 'vllm:spec_decode_num_accepted_tokens_total'):
        vals = [float(x) for x in re.findall(r'^' + re.escape(key) + r'(?:\{[^}]*\})? ([0-9.eE+]+)$', m, re.M)]
        out[key] = sum(vals) if vals else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--model', required=True)
    ap.add_argument('--kind', choices=('vllm', 'llamacpp'), required=True); ap.add_argument('--vision', action='store_true')
    a = ap.parse_args()
    res = {'base': a.base, 'model': a.model, 'kind': a.kind, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'checks': {}}
    ok = True

    def check(name, passed, **info):
        nonlocal ok
        res['checks'][name] = dict(passed=bool(passed), **info); ok &= bool(passed)
        print(('PASS ' if passed else 'FAIL ') + name + ' ' + json.dumps(info)[:300], flush=True)

    # 1 correctness
    d, _ = chat(a, 'What is 17 multiplied by 23? Answer with just the number.', 16)
    ans = d['choices'][0]['message']['content']
    check('correctness_arithmetic', '391' in ans, answer=ans.strip()[:60])
    d, _ = chat(a, 'What is the capital of Australia? One word.', 8)
    ans = d['choices'][0]['message']['content']
    check('correctness_fact', 'canberra' in ans.lower(), answer=ans.strip()[:60])

    # 2 determinism
    q = 'List five prime numbers greater than 100, comma separated, nothing else.'
    r1 = chat(a, q, 40)[0]['choices'][0]['message']['content']; r2 = chat(a, q, 40)[0]['choices'][0]['message']['content']
    check('determinism_greedy_repeat', r1 == r2, first=r1.strip()[:80])

    # 3 prompt caching (long shared prefix, unique tail so the cache is exercised, not a full-response replay)
    para = ('The quick survey of distributed systems covers consensus, replication, partitioning, clocks, and failure detection. '
            'Each topic trades latency, availability, and consistency in different ways. ') * 260
    base_prompt = 'Read this background carefully.\n\n' + para + '\n\nQuestion: '
    ttft1, text1, _ = stream_ttft(a, base_prompt + 'name the first topic listed.', 24)
    d_cached, _ = chat(a, base_prompt + 'name the first topic listed.', 24)
    ttft2, text2, _ = stream_ttft(a, base_prompt + 'name the first topic listed.', 24)
    usage = d_cached.get('usage') or {}
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
    if a.kind == 'llamacpp':
        cached = (d_cached.get('timings') or {}).get('cache_n', cached)
    check('prompt_cache_hit', (cached or 0) >= 0.7 * (usage.get('prompt_tokens') or 1) and (ttft2 or 9e9) < (ttft1 or 0), cached_tokens=cached,
          prompt_tokens=usage.get('prompt_tokens'), ttft_cold_s=round(ttft1 or -1, 3), ttft_warm_s=round(ttft2 or -1, 3))
    check('prompt_cache_output_identical', text1 == text2 == d_cached['choices'][0]['message']['content'], answer=text1.strip()[:60])

    # 4 MTP + speed
    before = mtp_counters(a)
    d, wall = chat(a, 'Write a detailed 400-word explanation of how a hash map works, including collisions and resizing.', 512)
    n = (d.get('usage') or {}).get('completion_tokens') or 0
    tim = d.get('timings') or {}
    after = mtp_counters(a)
    if a.kind == 'vllm':
        acc = (after or {}).get('vllm:spec_decode_num_accepted_tokens_total'); acc0 = (before or {}).get('vllm:spec_decode_num_accepted_tokens_total')
        dr = (after or {}).get('vllm:spec_decode_num_draft_tokens_total'); dr0 = (before or {}).get('vllm:spec_decode_num_draft_tokens_total')
        accepted = (acc or 0) - (acc0 or 0); drafted = (dr or 0) - (dr0 or 0)
        check('mtp_active', drafted > 0 and accepted > 0, drafted=drafted, accepted=accepted,
              acceptance=round(accepted / drafted, 3) if drafted else None)
        rate = n / wall if wall else 0
    else:
        drafted = tim.get('draft_n'); accepted = tim.get('draft_n_accepted')
        check('mtp_active', (drafted or 0) > 0 and (accepted or 0) > 0, drafted=drafted, accepted=accepted)
        rate = tim.get('predicted_per_second') or (n / wall if wall else 0)
    check('decode_speed_reported', n >= 200, completion_tokens=n, tok_per_s=round(rate, 2), wall_s=round(wall, 2))
    res['decode_tok_per_s'] = round(rate, 2)

    # 5 vision
    if a.vision:
        img = base64.b64encode(png()).decode()
        content = [{'type': 'text', 'text': 'What is the main background color of this image, and what color is the small square in the top-right corner? Answer in one short sentence.'},
                   {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + img}}]
        d, _ = chat(a, content, 40)
        ans = d['choices'][0]['message']['content'].lower()
        check('vision_colors', 'red' in ans and 'blue' in ans, answer=ans.strip()[:100])

    res['passed'] = ok
    out = Path(__file__).with_name('validation-' + a.model + '-' + res['utc'].replace(':', '') + '.json')
    out.write_text(json.dumps(res, indent=2) + '\n')
    print(('ALL PASS' if ok else 'SOME CHECKS FAILED') + ' -> ' + str(out))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
