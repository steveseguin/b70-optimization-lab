# Bytes a decode step reads: every tensor once except routed experts (6 of E per layer) and the embedding tables.
import sys, re, glob
from gguf import GGUFReader
files = sorted(glob.glob(sys.argv[1] + '/*.gguf'))
cls = {}
E = None
for f in files:
    r = GGUFReader(f)
    for t in r.tensors:
        n = t.name; b = int(t.n_bytes)
        if '_exps' in n:
            E = int(t.shape[-1]) if E is None else E
            k = 'routed (all)'
        elif 'token_embd' in n: k = 'embeddings (not read per step)'
        elif n.startswith('output.'): k = 'head'
        elif 'attn' in n or 'indexer' in n: k = 'attention'
        elif 'shexp' in n: k = 'shared expert'
        else: k = 'other'
        cls[k] = cls.get(k, 0) + b
print('experts per layer', E)
for k, v in sorted(cls.items(), key=lambda x: -x[1]): print(f'{k:34s} {v/1e9:8.3f} GB')
act = sum(v for k, v in cls.items() if not k.startswith('routed') and not k.startswith('embed')) + cls['routed (all)'] * 6 / E
print(f'read per step (all cards): {act/1e9:.3f} GB; per card {act/6e9:.3f} GB')
