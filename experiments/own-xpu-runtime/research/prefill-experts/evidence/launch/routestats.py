import struct,sys,collections,math
f=open(sys.argv[1],'rb').read(); off=0
recs=collections.defaultdict(list)   # label -> list of (M, routes[slots])
nonstd=0; total=0
while off<len(f):
    (ln,)=struct.unpack_from('<I',f,off); off+=4
    label=f[off:off+ln].decode(); off+=ln
    M,slots=struct.unpack_from('<II',f,off); off+=8
    r=struct.unpack_from('<%dI'%(3*slots),f,off); off+=12*slots
    routes=[(r[3*i],r[3*i+1],r[3*i+2]) for i in range(slots)]
    recs[label].append((M,routes))
labels=sorted(recs,key=lambda s:(int(s.split('.')[1]),s))
print('sites',len(labels),'chunks/site',len(recs[labels[0]]))
rowsof={}
for lab in labels:
    for M,rt in recs[lab]:
        for e,b,c in rt:
            total+=1
            if b!=0: nonstd+=1
            rowsof.setdefault(lab,set()).add(c)
print('routes',total,'nonzero row_begin',nonstd,'row_counts',{k:v for k,v in list(rowsof.items())[:3]})
# gate vs down experts equal?
same=all([e for e,_,_ in a[1]]==[e for e,_,_ in b[1]] for lab in labels if lab.endswith('expsgate') for a,b in zip(recs[lab],recs[lab.replace('expsgate','expsdown')]))
print('down experts == gate experts:',same)
gates=[l for l in labels if l.endswith('expsgate')]
# per-token expert lists per layer
tok={}
for lab in gates:
    seq=[]
    for M,rt in recs[lab]:
        for t in range(M): seq.append([rt[t*10+j][0] for j in range(10)])
    tok[lab]=seq
N=len(tok[gates[0]])
print('tokens',N,'layers',len(gates))
print('%6s %8s %8s %9s %9s %9s %9s'%('chunk','slots','distinct','slots/exp','T4 fill','T8 fill','max/exp'))
for C in (32,64,128,256,512,1024):
    d=[];fill4=[];fill8=[];mx=[]
    for lab in gates:
        seq=tok[lab]
        for c0 in range(0,N-C+1,C):
            cnt=collections.Counter(e for t in seq[c0:c0+C] for e in t)
            n=C*10; d.append(len(cnt)); mx.append(max(cnt.values()))
            fill4.append(n/sum(math.ceil(v/4) for v in cnt.values())/4); fill8.append(n/sum(math.ceil(v/8) for v in cnt.values())/8)
    k=len(d)
    print('%6d %8d %8.1f %9.2f %9.2f %9.2f %9.1f'%(C,C*10,sum(d)/k,C*10/(sum(d)/k),sum(fill4)/k,sum(fill8)/k,sum(mx)/k))
# expert popularity skew in one layer
lab=gates[0]; cnt=collections.Counter(e for t in tok[lab] for e in t)
v=sorted(cnt.values(),reverse=True); print(lab,'experts used',len(cnt),'top10 share %.3f'%(sum(v[:10])/sum(v)),'top50 %.3f'%(sum(v[:50])/sum(v)))
