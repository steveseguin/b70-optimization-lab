import sys, re, statistics as st
lines = open(sys.argv[1]).read().splitlines()
mi = [i for i,l in enumerate(lines) if l.startswith('M per check:')][0]
M = eval(lines[mi].split(':',1)[1])
hdr = mi + 1
rows = {}
for l in lines[hdr+1:]:
    p = l.split()
    if len(p) < len(M) + 1: continue
    name = ' '.join(p[:len(p)-len(M)-1]) if len(p) > len(M)+1 else p[0]
    vals = [float(v) for v in p[len(p)-len(M)-1:len(p)-1]]
    rows[name] = vals
def cat(n):
    if n.startswith('TOTAL'): return None
    if re.search(r'Xchg', n): return 'exchanges'
    if re.search(r'Routed|RoutePM|ExpertGroup|MoeCombine|Swiglu|RoutePRows', n): return 'experts+router'
    if re.search(r'Sparse|OutMJ|Score|Attn|Window|Cidx|Indexer|TopK', n): return 'attention'
    if re.search(r'Norm|HcPostPre|Dots(?!Rows\+Dense)', n) and not re.search(r'Dense|Gemv', n): return 'norms+mix'
    if re.search(r'Dense|Gemv|PaceK|FlDownComb|RowsDotsK', n): return 'dense rows'
    return 'other'
cats = {}
for n, v in rows.items():
    c = cat(n)
    if c is None: continue
    cats.setdefault(c, [0.0]*len(M))
    cats[c] = [a+b for a,b in zip(cats[c], v)]
tot = rows.get('TOTAL busy') or rows.get('TOTAL')
Ms = sorted(set(M))
print('part'.ljust(16) + ''.join(f'M={m}'.rjust(9) for m in Ms))
for c in ['dense rows','experts+router','exchanges','attention','norms+mix','other']:
    if c not in cats: continue
    print(c.ljust(16) + ''.join(f'{st.median([cats[c][i] for i in range(len(M)) if M[i]==m])/1000:9.2f}' for m in Ms))
print('total'.ljust(16) + ''.join(f'{st.median([tot[i] for i in range(len(M)) if M[i]==m])/1000:9.2f}' for m in Ms))
print('checks'.ljust(16) + ''.join(f'{M.count(m):9d}' for m in Ms))
for c in ['other']:
    if c in cats: print('other families:', [n for n in rows if cat(n)=='other'])
