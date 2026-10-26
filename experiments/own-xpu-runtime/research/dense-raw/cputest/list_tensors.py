#!/usr/bin/env python3
"""Affected tensors of OWNRT_DENSE_RAW for SC117 (GSQ mode): the logits head plus every weight named in the p33
attention-Q8 / QKV-Q6 / dense-Q6 policies, with their GGUF location. Output TSV: name shard offset bytes type rows cols."""
import json, re, sys
from pathlib import Path
SRC = Path(sys.argv[1])   # engine/src
gg = {x['name']: x for x in json.load(open(sys.argv[2]))}
names = ['output.weight']
for f in ['gsq-rco-iq3s/qkv-q6-p33/engine/build/source/policy.hpp', 'gsq-rco-iq3s/dense-q6-p33/build/source/policy.hpp']:
    names += re.findall(r'\{"blk\.\d+\.[a-z.]+","(blk\.\d+\.[a-z_]+\.weight)"', (SRC / f).read_text())
assert len(names) == 1 + 48 + 22 + 19 and len(set(names)) == len(names), len(names)
for n in names:
    t = gg[n]; cols, rows = t['dims']
    print(n, t['file'], t['offset'], t['bytes'], t['type'], rows, cols, sep='\t')
