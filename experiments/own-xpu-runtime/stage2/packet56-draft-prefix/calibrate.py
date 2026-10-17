#!/usr/bin/env python3
"""Apply the committed text-only rule; read admitted GGUF headers, never weights."""
import collections
import hashlib
import json
import os
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
AUTHORITY = P.parent / 'packet49c-round2/build/input'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32))
    rule_raw = (P / 'calibration/preregistration.json').read_bytes()
    rule = json.loads(rule_raw)
    # Selection cannot be silently replaced after examining benchmark outputs.
    destination = P / 'calibration/selection.json'
    assert not destination.exists(), 'selection already frozen'
    sys.path.insert(0, str(ROOT / 'experiments/own-xpu-runtime/stage1/packet1b'))
    from loaders.headers import gguf_header
    tok_path = ROOT / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
    sys.path.insert(0, str(tok_path))
    from tokenizer import Tokenizer
    authority = json.loads((AUTHORITY / 'input.json').read_bytes())
    model = Path(authority['model_dir'])
    for line in (AUTHORITY / 'identity.tsv').read_text().splitlines():
        name, *identity = line.split()
        st = (model / name).stat()
        assert (st.st_size, st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns) == tuple(map(int, identity))
    shard = next(model.glob('*00001-of-00003.gguf'))
    with shard.open('rb') as f:
        header = gguf_header(f, shard.stat().st_size)
    with shard.open('rb') as f:
        header_hash = sha(f.read(header['header_bytes_read']))
    assert header_hash == authority['header_sha256']
    tokenizer = Tokenizer(header['metadata'])
    counts = collections.Counter()
    sources = []
    for entry in rule['sources']:
        raw = (ROOT / entry['path']).read_bytes()
        assert sha(raw) == entry['sha256'] and len(raw) == entry['bytes']
        text = raw.decode('utf-8')
        ids = tokenizer.encode(text)
        assert tokenizer.decode(ids) == text
        counts.update(ids)
        sources.append(dict(entry, tokens=len(ids), token_ids_sha256=sha(json.dumps(ids, separators=(',', ':')).encode())))
    total = sum(counts.values())
    vocab = len(tokenizer.tokens)
    alignment = rule['row_alignment']
    covered = 0
    for n in range(alignment, vocab + alignment, alignment):
        n = min(n, vocab)
        covered = sum(v for k, v in counts.items() if k < n)
        if covered * rule['coverage_denominator'] >= total * rule['coverage_numerator']:
            break
    previous = sum(v for k, v in counts.items() if k < n - alignment)
    result = dict(schema='lab.packet56.draft-prefix-selection.v1',
                  preregistration_sha256=sha(rule_raw), draft_vocab_rows=n,
                  full_vocab_rows=vocab, row_alignment=alignment, tokens=total,
                  covered_tokens=covered, excluded_tokens=total-covered,
                  coverage=covered/total, excluded_fraction=(total-covered)/total,
                  previous_aligned_rows=n-alignment, previous_coverage=previous/total,
                  sources=sources, header_sha256=header_hash,
                  header_bytes_read=2*header['header_bytes_read'], model_payload_bytes_read=0,
                  tokenizer_sha256=sha((tok_path / 'tokenizer.py').read_bytes()),
                  histogram={str(k): v for k, v in sorted(counts.items())},
                  scope='Independent local text tokens; not generated-target acceptance or benchmark coverage')
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','histogram')}))


if __name__ == '__main__':
    main()
