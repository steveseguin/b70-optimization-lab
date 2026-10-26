import json,sys,collections
f=sys.argv[1]; N=int(sys.argv[2]) if len(sys.argv)>2 else 7; skip=int(sys.argv[3]) if len(sys.argv)>3 else 7
L=[json.loads(l) for l in open(f)]
acc=collections.defaultdict(lambda: collections.defaultdict(list))
for l in L:
    c=l.get('chunk',0)
    if c<skip: continue
    for k,v in l['sites'].items(): acc[k][c%N].append(v['ms'])
names={7:['2x8','1x16','2x16g','1x32g','4x8g','2x32g','canon'],8:['2x8','1x16','2x16g','1x32g','4x8g','4x16g','1x4','canon'],13:['2x8','1x16','2x16g','1x32g','4x8g','4x16g','1x4','2x4','1x1','8x4g','4x8gO','2x16gO','canon'],16:['2x8','1x16','2x16g','1x32g','4x8g','4x16g','1x4','2x4','1x1','8x4g','4x8gO','2x16gO','4x8H','2x16HO','4x8HO','canon']}.get(N,[str(i) for i in range(N)])
keys=sorted(k for k in acc if k.startswith('gemv'))
print('%-22s'%'site(ms/chunk)'+''.join('%7s'%n for n in names))
tot=[0]*N
for k in keys:
    row=[sum(acc[k][i])/len(acc[k][i]) if acc[k][i] else float('nan') for i in range(N)]
    for i in range(N): tot[i]+=row[i]
    print('%-22s'%k[5:]+''.join('%7.3f'%x for x in row))
print('%-22s'%'TOTAL gemv'+''.join('%7.2f'%x for x in tot))
other=collections.defaultdict(float)
for k in acc:
    if not k.startswith('gemv'):
        for i in range(N):
            if acc[k][i]: other[i]+=sum(acc[k][i])/len(acc[k][i])
print('%-22s'%'other sites'+''.join('%7.1f'%other[i] for i in range(N)))
