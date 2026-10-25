#!/usr/bin/env python3
"""Run the fixed 12-prompt realistic suite once each (cold, 512 cap, greedy) through the LAN service; record MTP stats."""
import argparse, hashlib, importlib.util, json, math, statistics, time, urllib.request
from pathlib import Path
R = Path('/home/steve/llm-optimizations'); L = R / 'experiments/own-xpu-runtime/gsq-rco-iq3s'
SUITE = R / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012'
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def response_row(res, prompt_id, ids, wall_s):
    """Require explicit cold-request evidence and retain the service timing window."""
    try:
        cached = res['usage']['prompt_tokens_details']['cached_tokens']
    except (KeyError, TypeError) as exc:
        raise ValueError(prompt_id + ': explicit cached_tokens metadata is required') from exc
    if type(cached) is not int or cached != 0:
        raise ValueError(prompt_id + ': cached_tokens must be the integer 0 (cold request)')
    o = res['ownrt']; content = res['choices'][0]['message']['content']
    count, duration, rate = o['output_tokens'], o.get('decode_wall_ms'), o.get('decode_tok_s')
    if type(count) is not int or count < 2:
        raise ValueError(prompt_id + ': at least two output tokens are required for decode timing')
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (duration, rate)):
        raise ValueError(prompt_id + ': positive finite decode_wall_ms and decode_tok_s are required')
    numerator = count - 1
    recomputed = numerator * 1000 / duration
    if not math.isclose(rate, recomputed, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(prompt_id + ': decode rate does not match full-response interval accounting')
    return dict(prompt_id=prompt_id, prompt_tokens=len(ids), output_tokens=count,
                finish=res['choices'][0]['finish_reason'], cached_tokens=cached,
                mtp=o['mtp'], acceptance=o['mtp']['hits'] / o['mtp']['guesses'] if o['mtp']['guesses'] else None,
                decode_tok_s=rate, decode_wall_ms=duration, decode_numerator=numerator,
                decode_intervals=numerator, decode_event_count=count,
                decode_numerator_source='output_tokens - 1, per service native-controller definition',
                decode_window='first to last generated-token completion over the full response; not first-99 intervals',
                decode_timestamp_source='service aggregate; individual completion timestamps are not present in this response',
                recomputed_decode_tok_s=recomputed,
                prompt_wall_ms=o['prompt_wall_ms'], wall_s=wall_s,
                output_sha256=hashlib.sha256(content.encode()).hexdigest(),
                prompt_token_ids=ids, output_token_ids=o.get('output_token_ids'), activations=o.get('activations'))


def summarize(rows, label, url):
    g = sum(r['mtp']['guesses'] for r in rows); h = sum(r['mtp']['hits'] for r in rows)
    return dict(label=label, url=url, prompts=len(rows), pooled_acceptance=h / g if g else None, guesses=g, hits=h,
                median_decode_tok_s=statistics.median(r['decode_tok_s'] for r in rows),
                median_definition='conventional median across prompt rates; mean of the middle two for an even count; not class-balanced',
                rows=rows,
                scope='one cold request per frozen suite prompt, 512 cap, greedy; service observation, not a certified benchmark')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--url', default='http://192.168.2.44:18160/v1/chat/completions'); ap.add_argument('--label', required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    C = load(L / 'serving/lan/chat.py', 'suite_chat'); chat = C.Chat()
    manifest = json.loads((SUITE / 'suite-manifest.json').read_text())
    rows = []
    for p in manifest['prompts']:
        ids = list(map(int, (SUITE / p['prompt_id'] / 'tokens.txt').read_text().split()))
        text = chat.tok.decode(ids, skip_special_tokens=False)
        user = text.split('<|im_start|>user\n', 1)[1].split('<|im_end|>', 1)[0]
        msgs = [{'role': 'user', 'content': user}]
        if 'system\n' in text.split('<|im_start|>user', 1)[0]:
            msgs.insert(0, {'role': 'system', 'content': text.split('<|im_start|>system\n', 1)[1].split('<|im_end|>', 1)[0]})
        req = C.parse({'messages': msgs, 'max_tokens': 512}, chat)
        if req['prompt_ids'] != ids:
            raise ValueError(p['prompt_id'] + ': re-rendered prompt differs from the frozen suite tokens')
        body = json.dumps({'messages': msgs, 'max_tokens': 512}).encode()
        t0 = time.monotonic()
        with urllib.request.urlopen(urllib.request.Request(a.url, data=body, headers={'Content-Type': 'application/json'}), timeout=900) as r:
            res = json.load(r)
        rows.append(response_row(res, p['prompt_id'], ids, time.monotonic() - t0))
        print(json.dumps({k: v for k, v in rows[-1].items() if not k.endswith('token_ids')}), flush=True)
    summary = summarize(rows, a.label, a.url)
    a.out.write_text(json.dumps(summary, indent=1) + '\n'); print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
