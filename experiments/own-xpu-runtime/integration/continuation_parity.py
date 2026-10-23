#!/usr/bin/env python3
"""Rendering-parity harness, step 3 (2026-10-23): is prompt + generated ids a prefix of the next turn?

A parked session's checkpoint holds the engine's token history: the request's prompt ids followed by the ids it
generated (SESSION-SWAP-DESIGN.md §5, ctxkeeper parking.py). The next request is a message list rendered by the
chat template and tokenized afresh, so a restore is possible only if that rendering reproduces the generated ids
in place. Two things can break it: the template trims a stored assistant turn (`|trim`) and wraps it in the
think block, and re-tokenizing decoded text need not give the same ids the engine produced.

This harness takes every one-card device run that recorded generated ids (packets 178-181, 12 prompts each,
fixed 512-token greedy generations), decodes the ids with the pinned oracle tokenizer and the header vocabulary,
renders [user: raw prompt, assistant: decoded reply, user: "Continue."] with the pinned template, tokenizes the
result, and reports how many of the generated ids survive as an exact prefix. CPU only, read-only.

Usage: continuation_parity.py --gguf shard1.gguf [--out receipt.json]   (needs jinja2, regex)
"""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

from jinja2.sandbox import ImmutableSandboxedEnvironment

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
ORACLE = LAB / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
SUITE = LAB / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
RECORDS = LAB / 'experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/lineage/input-metadata'
RUNS = sorted(LAB.glob('experiments/own-xpu-runtime/stage2/packet1[78][0-9]-*/one-card/evidence/*/summary.json'))
TEMPLATE = HERE / 'chat_template-7c1460a9.jinja'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def common(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--gguf', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    rp = load('render_parity', HERE / 'render_parity.py')
    tok = load('oracle_tokenizer', ORACLE / 'tokenizer.py').Tokenizer(rp.meta_from_gguf(Path(a.gguf)))
    env = ImmutableSandboxedEnvironment()
    template = TEMPLATE.read_text()
    raw = {p['id']: p['prompt'] for p in json.loads(SUITE.read_text())['prompts']}
    prompt_ids = {}
    for rec in RECORDS.glob('*/input.json'):
        d = json.loads(rec.read_text())
        prompt_ids[Path(d['prompt']).stem] = d['tokens']
    receipt = {'schema': 'own-runtime.continuation-parity.v1', 'template_sha256': hashlib.sha256(template.encode()).hexdigest(),
               'tokenizer_source_sha256': hashlib.sha256((ORACLE / 'tokenizer.py').read_bytes()).hexdigest(),
               'next_user_message': 'Continue.', 'runs': [], 'generated_total': 0, 'generated_reproduced': 0, 'requests': 0, 'exact': 0}
    for summary in RUNS:
        d = json.loads(summary.read_text())
        run = {'packet': summary.parts[-5], 'run': summary.parts[-2], 'requests': []}
        for r in d.get('requests', []):
            if not isinstance(r.get('tokens'), list):
                continue
            pid = r['prompt_id']
            prompt, gen = prompt_ids[pid], r['tokens']
            reply = tok.decode(gen)
            nxt = env.from_string(template).render(
                messages=[{'role': 'user', 'content': raw[pid]}, {'role': 'assistant', 'content': reply}, {'role': 'user', 'content': 'Continue.'}],
                add_generation_prompt=True, enable_thinking=False)
            ids = tok.encode(nxt)
            held = prompt + gen
            n = common(held, ids)
            kept = max(0, n - len(prompt))
            row = {'prompt_id': pid, 'prompt_tokens': len(prompt), 'generated': len(gen), 'generated_reproduced': kept,
                   'exact': kept == len(gen), 'prompt_reproduced': n >= len(prompt),
                   'reply_starts_with_space': reply[:1].isspace(), 'reply_ends_with_space': reply[-1:].isspace(),
                   'reply_has_im_end': any(t == 248046 for t in gen)}
            if not row['exact']:
                k = len(prompt) + kept
                row['first_difference'] = {'at': k, 'held': held[k:k + 3], 'rendered': ids[k:k + 3],
                                           'held_text': tok.decode(held[k:k + 3]), 'rendered_text': tok.decode(ids[k:k + 3]),
                                           'generated_left': len(gen) - kept}
            run['requests'].append(row)
            receipt['requests'] += 1; receipt['exact'] += row['exact']
            receipt['generated_total'] += len(gen); receipt['generated_reproduced'] += kept
        receipt['runs'].append(run)
    receipt['exact_share'] = f"{receipt['exact']}/{receipt['requests']}"
    receipt['generated_share'] = f"{receipt['generated_reproduced']}/{receipt['generated_total']}"
    if a.out:
        Path(a.out).write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"requests {receipt['requests']}: prompt+generated is an exact prefix of the next turn in {receipt['exact_share']}; "
          f"generated ids reproduced {receipt['generated_share']}")
    seen = set()
    for run in receipt['runs']:
        for row in run['requests']:
            if not row['exact'] and row['prompt_id'] not in seen:
                seen.add(row['prompt_id'])
                fd = row['first_difference']
                print(f"  {row['prompt_id']}: {row['generated_reproduced']}/{row['generated']} kept; at {fd['at']} held {fd['held_text']!r} vs rendered {fd['rendered_text']!r}; "
                      f"starts_space={row['reply_starts_with_space']} ends_space={row['reply_ends_with_space']} im_end={row['reply_has_im_end']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
