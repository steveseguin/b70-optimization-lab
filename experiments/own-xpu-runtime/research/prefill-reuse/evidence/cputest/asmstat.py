import re,sys,glob,collections
for f in sorted(glob.glob(sys.argv[1]+'/*.asm')):
    txt=open(f).read()
    m=re.search(r'_ZTSN6reuse24Tile\w+',txt)
    if not m: continue
    name=m.group(0).replace('_ZTSN6reuse24TileINS_','')
    if len(sys.argv)>2 and not re.search(sys.argv[2],name): continue
    blocks=re.split(r'\n// (B\d+):',txt)
    spill=re.search(r'spill[^\n]*',txt[:3000])
    best=None
    for i in range(1,len(blocks),2):
        body=blocks[i+1]
        ops=collections.Counter()
        for line in body.split('\n'):
            mm=re.match(r'\s*(?:\([^)]*\)\s*)?([a-z][\w.]*)\s+(?:\([^)]*\)\s*)?\((\d+)\|M\d+\)',line)
            if mm: ops[mm.group(1)+'/'+mm.group(2)]+=1
        tot=sum(ops.values())
        if best is None or tot>best[0]: best=(tot,blocks[i],ops)
    tot,b,ops=best
    fp=ops['mul/32']+ops['add/32']
    print(f"{name:60s} body {b} instr {tot:4d} mul32 {ops['mul/32']:3d} add32 {ops['add/32']:3d} loads {sum(v for k,v in ops.items() if k.startswith('load')):3d} other {tot-fp:4d}", '|', ' '.join(f"{k}={v}" for k,v in ops.most_common(8) if not k.startswith(('mul/32','add/32'))))
