import sys, collections, json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('/model')
text = open('/work/corpus.txt', errors='ignore').read()
counts = collections.Counter()
step = 200000; total = 0
for i in range(0, len(text), step):
    ids = tok(text[i:i+step], add_special_tokens=False)['input_ids']
    counts.update(ids); total += len(ids)
vocab = len(tok)
ranked = [t for t, _ in counts.most_common()]
special = [i for i in tok.all_special_ids]
print(f"corpus tokens {total}, distinct {len(counts)}, tokenizer vocab {vocab}, special {len(special)}")
for N in (8192, 16384, 32768, 65536):
    S = sorted(set(ranked[:N]) | set(special))
    cov = sum(counts[t] for t in S) / total
    open(f'/work/shortlist-top{N}.txt', 'w').write('\n'.join(map(str, S)) + '\n')
    print(f"top{N}: {len(S)} ids, corpus coverage {cov*100:.2f}%")
