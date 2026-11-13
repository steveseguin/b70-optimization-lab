"""role sums per card and M from forms_by_m.py output (all names, threshold 0); roles by kernel name"""
import sys, re, collections
f = sys.argv[1]; cards = [int(c) for c in sys.argv[2].split(',')]
cur = None; T = collections.defaultdict(dict)
for l in open(f):
    m = re.match(r'== card (\d) M=(\d)', l)
    if m: cur = (int(m.group(1)), int(m.group(2))); continue
    p = l.split(None, 3)
    if len(p) < 4: continue
    T[cur][p[3].strip()] = (float(p[0]), float(p[1]), float(p[2]))
def role(n):
    if n.startswith('Xchg'): return 'xchg'
    if 'Routed' in n or 'ExpertGroup' in n or 'Swiglu' in n or 'MoeCombine' in n: return 'experts'
    if 'Sparse' in n or 'Window' in n or 'Cidx' in n or 'PubAppend' in n: return 'attention'
    if 'PaceSQ8<40' in n or 'PaceSQ6<5,' in n or 'WsQ8<40>' in n or 'WsQ6<5>' in n or 'GemvQ8P<40,' in n or 'GemvQ6KP<5,' in n: return 'q_b'
    if 'PaceSQ8<128' in n or 'PaceSQ6<16' in n or 'WsQ8<128>' in n or 'WsQ6<16>' in n or 'GemvQ8P<128,' in n or 'GemvQ6KP<16,' in n: return 'o_a'
    if 'WsQ8<256>' in n or 'WsQ6<32>' in n or 'GemvQ8P<256,' in n or 'GemvQ6KP<32,' in n: return 'o_b'
    if 'WsQ8<72>' in n or 'WsQ5<9>' in n or 'GemvQ8P<72,' in n or 'GemvQ5KP<9,' in n: return 'sh_down'
    if n.startswith('RoutePM'): return 'shared_gu'
    if 'WsQ6<24>' in n or 'GemvQ6KP<24' in n: return 'engram'
    if ('WsQ8<160>' in n or 'WsQ6<20>' in n or 'GemvQ8P<160,' in n or 'GemvQ6KP<20,' in n) and 'RowsPair' in n: return 'qkv'
    if 'WsQ6<20>' in n or 'GemvQ6KP<20' in n: return 'head'
    if 'GemvQ8P<480' in n: return 'draft_in(15360)'
    if 'GemvQ8P<160' in n: return 'q8_5120_single'
    if 'GemvH16P<160' in n or 'FlNormKM' in n or 'RowsDots' in n: return 'router(+norm/dots)'
    if 'EngRows' in n or 'Embed' in n or 'Broadcast' in n: return 'host-fed'
    if 'Norm' in n or 'HcPost' in n or 'HcPre' in n or 'Dots' in n: return 'norms+mix'
    return 'other'
roles = collections.defaultdict(lambda: collections.defaultdict(float)); cnt = collections.defaultdict(lambda: collections.defaultdict(float))
for k, v in T.items():
    for n, (us, c, per) in v.items(): roles[k][role(n)] += us; cnt[k][role(n)] += c
R = sorted(set(r for k in roles for r in roles[k]))
Ms = sorted(set(k[1] for k in roles))
for m in Ms:
    print(f'M={m}: role (us/check: sum of per-name medians; launches)  ' + '  '.join(f'c{c}' for c in cards))
    for r in R:
        print(f'   {r:20s}' + ''.join(f'{roles[(c, m)].get(r, 0):7.0f}' for c in cards) + f'   n={cnt[(cards[0], m)].get(r, 0):.0f}')
    print(f'   {"TOTAL":20s}' + ''.join(f'{sum(roles[(c, m)].values()):7.0f}' for c in cards))
