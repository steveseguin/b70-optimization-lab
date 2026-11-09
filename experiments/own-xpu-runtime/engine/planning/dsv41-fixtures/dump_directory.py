# Emits a directory TSV (name grid dims bytes component) for the dsv41
# backbone shards, consumed by test_directory_v41.cpp via read_directory.
import sys
from gguf import GGUFReader

BLOCK = {0: (1, 4), 1: (1, 2), 8: (32, 34), 10: (256, 84), 11: (256, 110),
         12: (256, 144), 13: (256, 176), 14: (256, 210), 16: (256, 66),
         17: (256, 74), 18: (256, 98), 19: (256, 50), 20: (32, 18),
         21: (256, 110), 22: (256, 82), 23: (256, 136), 30: (1, 2),
         39: (32, 17), 42: (64, 18)}
NAMES = {0: 'F32', 1: 'F16', 8: 'Q8_0', 10: 'Q2_K', 11: 'Q3_K', 12: 'Q4_K',
         13: 'Q5_K', 14: 'Q6_K', 16: 'IQ2_XXS', 17: 'IQ2_XS', 18: 'IQ3_XXS',
         19: 'IQ1_S', 20: 'IQ4_NL', 21: 'IQ3_S', 22: 'IQ2_S', 23: 'IQ4_XS',
         30: 'BF16', 39: 'MXFP4', 42: 'Q2_0'}

base = '/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS'
seen = set()
for shard in ['00002', '00003', '00004', '00005', '00006']:
    r = GGUFReader(f'{base}/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-{shard}-of-00006.gguf')
    for t in r.tensors:
        if t.name in seen:
            continue
        seen.add(t.name)
        ty = int(t.tensor_type)
        elems, bts = BLOCK[ty]
        n = 1
        for d in t.shape:
            n *= int(d)
        dims = ','.join(str(int(x)) for x in t.shape)
        comp = 'engram' if t.name == 'per_layer_token_embd.weight' else (
            'layer' if t.name.startswith('blk.') else 'global')
        print(t.name, NAMES[ty], dims, n // elems * bts, comp)
