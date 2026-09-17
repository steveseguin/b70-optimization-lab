#!/usr/bin/env python3
"""Build an unrepeated prompt corpus for bench-prefill-followup.py from complete tracked repository files.

Each class (prose, code, docs) is the concatenation of distinct files, each used once, in the order given. The file
records repository-relative paths with SHA-256s, the concatenated text's SHA-256 and the token count under the
model's tokenizer, so a probe can state exactly which bytes it read and the tool can refuse lengths it cannot serve
without repetition.

usage: build-long-corpus.py --tokenizer /path/model --out corpus.json --min-tokens 45000 \\
         --prose a.md b.md --code x.py y.py --docs README.md ...
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLASSES = ('prose', 'code', 'docs')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tokenizer', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--min-tokens', type=int, default=45000)
    for cls in CLASSES:
        ap.add_argument(f'--{cls}', nargs='+', required=True, metavar='FILE')
    a = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    sources = []
    seen = set()
    for cls in CLASSES:
        parts, files = [], []
        for rel in getattr(a, cls):
            if rel in seen:
                raise SystemExit(f'{rel} used twice')
            seen.add(rel)
            data = (ROOT / rel).read_bytes()
            files.append({'path': rel, 'sha256': hashlib.sha256(data).hexdigest()})
            parts.append(data.decode('utf-8'))
        text = '\n\n'.join(parts)
        n = len(tok(text, add_special_tokens=False)['input_ids'])
        if n < a.min_tokens:
            raise SystemExit(f'{cls}: {n} tokens < {a.min_tokens}; add files')
        sources.append({'label': cls, 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                        'source_files': files, 'available_tokens': n})
        print(f'{cls}: {len(files)} files, {len(text)} chars, {n} tokens')
    if a.out.exists():
        raise SystemExit(f'refusing to overwrite {a.out}')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({'source_repetition': False,
                                 'scope': 'Continuation screen from complete distinct tracked source files, concatenated once; not a natural-completion quality suite.',
                                 'tokenizer': a.tokenizer, 'sources': sources}, indent=1) + '\n')
    print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
