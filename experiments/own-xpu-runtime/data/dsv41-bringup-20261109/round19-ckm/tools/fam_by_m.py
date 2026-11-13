import sys, statistics as st
# per-family median us by M from a dsv41_ck_by_m.py output (ck-by-m-cardN.txt)
lines = open(sys.argv[1]).read().splitlines()
mi = [i for i,l in enumerate(lines) if l.startswith('M per check:')][0]
M = eval(lines[mi].split(':',1)[1])
Ms = sorted(set(M))
rows = {}
for l in lines[mi+2:]:
    p = l.split()
    if len(p) < len(M) + 1: continue
    name = ' '.join(p[:len(p)-len(M)-1])
    vals = [float(v) for v in p[len(p)-len(M)-1:len(p)-1]]
    rows[name] = vals
out = []
for n, v in rows.items():
    med = [st.median([v[i] for i in range(len(M)) if M[i]==m]) for m in Ms]
    out.append((n, med))
out.sort(key=lambda x: -x[1][-1])
print('family'.ljust(44) + ''.join(f'M={m}'.rjust(8) for m in Ms) + ''.join(f'd{m}{m+1}'.rjust(7) for m in Ms[:-1]))
for n, med in out:
    if max(med) < float(sys.argv[2]) if len(sys.argv)>2 else 20: continue
    print(n[:44].ljust(44) + ''.join(f'{x:8.0f}' for x in med) + ''.join(f'{med[i+1]-med[i]:7.0f}' for i in range(len(med)-1)))
