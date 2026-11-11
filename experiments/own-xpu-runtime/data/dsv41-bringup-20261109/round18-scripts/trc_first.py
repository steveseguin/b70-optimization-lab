import struct, sys
TAGS = ["?", "embed", "engram", "attn_mix_pre", "attn_mix_post", "attn_mix_comb", "attn_in", "q", "kv",
        "cidx", "attn_o", "attn_oa", "attn_out", "streams_attn", "ffn_mix_pre", "ffn_in", "route_logits",
        "route_ids", "route_prob", "shared_down", "ffn_out", "streams_ffn", "final_n", "logits", "pub_ckv", "pub_ik"]
def read(p):
    out = []
    with open(p, 'rb') as f:
        while True:
            h = f.read(16)
            if len(h) < 16: break
            st, L, tag, n = struct.unpack('<4I', h)
            out.append((st, L, tag, f.read(4 * n)))
    return out
a, b = read(sys.argv[1]), read(sys.argv[2])
print(len(a), len(b))
shown = 0
for x, y in zip(a, b):
    if x[:3] != y[:3]:
        print('order differs', x[:3], y[:3]); break
    if x[3] != y[3]:
        n = len(x[3]) // 4
        fa = struct.unpack(f'<{n}f', x[3]); fb = struct.unpack(f'<{len(y[3])//4}f', y[3])
        nd = sum(1 for i in range(min(len(fa), len(fb))) if struct.pack('<f', fa[i]) != struct.pack('<f', fb[i]))
        idx = [i for i in range(min(len(fa), len(fb))) if struct.pack('<f', fa[i]) != struct.pack('<f', fb[i])][:6]
        print('step', x[0], 'layer', x[1], TAGS[x[2]] if x[2] < len(TAGS) else x[2], 'n', n, len(fb), 'differ', nd, 'first', [(i, fa[i], fb[i]) for i in idx])
        shown += 1
        if shown > 8: break
