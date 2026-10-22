#!/usr/bin/env python3
"""Rendering-parity harness, step 1 (2026-10-22): the exact token prefix a checkpoint is valid for.

The own runtime's checkpoints are valid only for an exact token prefix (SESSION-SWAP-DESIGN.md §5), and the
engine takes token ids, not messages. This harness encodes each sealed suite prompt (already rendered with the
chat template, `packet2-cpu-oracle/prompts/*.txt`) with the pinned oracle tokenizer
(`packet2-cpu-oracle/tokenizer.py`, sha256 pinned in the packets' tokenizer-identity.tsv) and compares the ids
with the token lists the sealed profile recorded (`lineage/input-metadata/*/input.json`, written by that same
tokenizer against the GGUF header). The vocabulary and merges come from a Hugging Face `tokenizer.json` on this
host because the GGUF shards are not here; their sha256 is recorded, and the 12/12 identity below is the evidence
that it is the same vocabulary. Messages -> rendered text (the chat template) is step 2 and is not covered here.

Usage: render_parity.py [--tokenizer /path/tokenizer.json] [--out receipt.json]   (CPU only, read-only)
"""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[3]
ORACLE = LAB / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
RECORDS = LAB / 'experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/lineage/input-metadata'
PINNED_TOKENIZER_SHA = '1c284c06b6a159c39cb9a00acd7cc411ed9adae87b4850e98da5dd4fd33543a7'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def meta_from_hf(tokenizer_json: Path) -> dict:
    """The GGUF-style metadata the oracle tokenizer expects, built from a Hugging Face tokenizer.json:
    tokens by id (gaps filled with an unreachable placeholder), merges as 'a b' strings, token types
    (3 = control for special added tokens, 4 = user-defined for other added tokens, 1 = normal)."""
    t = json.loads(tokenizer_json.read_text())
    vocab = dict(t['model']['vocab'])
    added = {a['id']: a for a in t.get('added_tokens', [])}
    n = max(max(vocab.values()), max(added) if added else -1) + 1
    tokens = [f'<unused-{i}>' for i in range(n)]
    types = [5] * n
    for s, i in vocab.items():
        tokens[i], types[i] = s, 1
    for i, a in added.items():
        tokens[i], types[i] = a['content'], 3 if a.get('special') else 4
    merges = [m if isinstance(m, str) else ' '.join(m) for m in t['model']['merges']]
    return {'tokenizer.ggml.pre': 'qwen35', 'tokenizer.ggml.tokens': tokens, 'tokenizer.ggml.merges': merges,
            'tokenizer.ggml.token_type': types}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--tokenizer', default='/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    tok_src = ORACLE / 'tokenizer.py'
    receipt = {'schema': 'own-runtime.render-parity.v1', 'oracle_tokenizer': {'path': str(tok_src), 'sha256': sha(tok_src),
               'pinned': PINNED_TOKENIZER_SHA, 'matches_pin': sha(tok_src) == PINNED_TOKENIZER_SHA},
               'vocabulary_source': {'path': a.tokenizer, 'sha256': sha(Path(a.tokenizer)), 'note': 'Hugging Face tokenizer.json on this host; the sealed records pin the GGUF header instead'},
               'prompts': [], 'passed': False}
    spec = importlib.util.spec_from_file_location('oracle_tokenizer', tok_src)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    tokenizer = mod.Tokenizer(meta_from_hf(Path(a.tokenizer)))
    ok = 0
    for rec in sorted(RECORDS.glob('*/input.json')):
        d = json.loads(rec.read_text())
        prompt = ORACLE / 'prompts' / Path(d['prompt']).name
        text = prompt.read_text()
        ids = tokenizer.encode(text)
        same = ids == d['tokens']
        ok += same
        first_diff = next((i for i, (x, y) in enumerate(zip(ids, d['tokens'])) if x != y), None if len(ids) == len(d['tokens']) else min(len(ids), len(d['tokens'])))
        receipt['prompts'].append({'name': rec.parent.name, 'prompt_sha256': sha(prompt), 'recorded_prompt_sha256': d['prompt_sha256'],
                                   'prompt_matches_record': sha(prompt) == d['prompt_sha256'], 'recorded_tokens': len(d['tokens']),
                                   'encoded_tokens': len(ids), 'identical': same, 'first_difference_at': first_diff,
                                   'record_header_sha256': d['header_sha256'], 'record_tokenizer_sha256': d['tokenizer_source_sha256']})
    receipt['passed'] = ok == len(receipt['prompts']) == 12 and receipt['oracle_tokenizer']['matches_pin'] and all(p['prompt_matches_record'] for p in receipt['prompts'])
    receipt['identical'] = f'{ok}/{len(receipt["prompts"])}'
    if a.out:
        Path(a.out).write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"oracle tokenizer matches pin: {receipt['oracle_tokenizer']['matches_pin']}; prompts identical to the sealed ids: {receipt['identical']}; passed: {receipt['passed']}")
    for p in receipt['prompts']:
        if not p['identical']:
            print('  DIFF', p['name'], 'recorded', p['recorded_tokens'], 'encoded', p['encoded_tokens'], 'first difference at', p['first_difference_at'])
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
