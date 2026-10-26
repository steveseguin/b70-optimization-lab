import json,sys,collections
f=sys.argv[1]; N=int(sys.argv[2]); names=sys.argv[3].split(',') if len(sys.argv)>3 else [str(i) for i in range(N)]
L=[json.loads(l) for l in open(f)]
acc=collections.defaultdict(lambda: collections.defaultdict(list))
for l in L:
    c=l.get('chunk',0)
    if c<N: continue
    for k,v in l['sites'].items(): acc[k][c%N].append(v['ms'])
rows=L[0]['rows']
print('%-26s'%('ms/chunk(%d rows)'%rows)+''.join('%8s'%n for n in names))
tot=[0]*N
for k in sorted(acc):
    if not k.startswith('routed'): continue
    row=[sum(acc[k][i])/len(acc[k][i]) if acc[k][i] else 0 for i in range(N)]
    for i in range(N): tot[i]+=row[i]
    print('%-26s'%k[12:]+''.join('%8.2f'%x for x in row))
print('%-26s'%'TOTAL routed'+''.join('%8.2f'%x for x in tot))
print('%-26s'%'routed ms/row'+''.join('%8.3f'%(x/rows) for x in tot))
o=[sum(sum(acc[k][i])/len(acc[k][i]) for k in acc if not k.startswith('routed') and acc[k][i]) for i in range(N)]
print('%-26s'%'other ms/row'+''.join('%8.3f'%(x/rows) for x in o))
print('samples',[len(acc[next(k for k in acc if k.startswith('routed'))][i]) for i in range(N)])
