import collections, json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('/model')
counts = collections.Counter(); totals = {}
for name in ('corpus.txt', 'corpus-system.txt', 'corpus-image-code.txt'):
    text = open(f'/work/{name}', errors='ignore').read(); n = 0
    for i in range(0, len(text), 200000):
        ids = tok(text[i:i+200000], add_special_tokens=False)['input_ids']; counts.update(ids); n += len(ids)
    totals[name] = n
print('tokens per source', totals, 'distinct', len(counts))
ranked = [t for t, _ in counts.most_common()]; special = list(tok.all_special_ids)
tot = sum(counts.values())
for N in (32768, 49152, 65536, 98304):
    S = sorted(set(ranked[:N]) | set(special)); open(f'/work/shortlist-v2-top{N}.txt', 'w').write('\n'.join(map(str, S)) + '\n')
    print(f'v2 top{N}: {len(S)} ids, corpus coverage {100*sum(counts[t] for t in S)/tot:.2f}%')
