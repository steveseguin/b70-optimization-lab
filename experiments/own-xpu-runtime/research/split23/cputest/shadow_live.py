# Liveness of batched-prefill row shadows (prefill_engine.hpp roles) over one chunk's site order; greedy slot packing.
import json,sys,re,collections
plan=json.load(open(sys.argv[1]));M=int(sys.argv[2])
bufs={b['name']:b['bytes'] for b in plan['buffers']}
def persistent(n):
    return n in('error','active','token_history','ple_metadata') or n.endswith('.state') or n.endswith('history') or n.endswith('.keys') or n.endswith('.values') or n.endswith('.raw') or n.endswith('.pooled')
def role(n):
    if not n.startswith('blk.'):return n
    d=n.find('.',4);return 'blk.*'+n[d:]
sites=[l for l in plan['launches'] if not(l['label'].startswith('final.') or l['label'] in('logits','argmax')) and l['op'] not in('handoff','handoff_result')]
rb=collections.defaultdict(int);events=collections.defaultdict(list) # role -> [(index,'w'|'r')]
for i,l in enumerate(sites):
    for kind,names in (('r',l['inputs']),('w',l['outputs'])):
        for n in names:
            if n in('position','token') or persistent(n):continue
            r=role(n);rb[r]=max(rb[r],bufs[n]);events[r].append((i,kind))
# segments: a value lives from a write to its last read before the next write (reads before any write: live from 0)
segs={}
for r,ev in events.items():
    s=[];start=None;last=None
    for i,k in ev:
        if k=='r':
            if start is None:start=0
            last=i
        else:
            if start is not None and last is not None:s.append((start,last))
            if start is not None and last is None:s.append((start,start))
            start=i;last=i
    if start is not None:s.append((start,max(last,start)))
    segs[r]=s
def overlap(a,b):
    return any(x0<=y1 and y0<=x1 for x0,x1 in a for y0,y1 in b)
total=sum(rb.values())*M
slots=[] # [size, roles, segs]
for r in sorted(rb,key=lambda r:-rb[r]):
    best=None
    for s in slots:
        if not any(overlap(segs[r],segs[q]) for q in s[1]):
            if best is None or s[0]<best[0]:best=s
    if best is None:slots.append([rb[r],[r]])
    else:best[1].append(r);best[0]=max(best[0],rb[r])
packed=sum(s[0] for s in slots)*M
print('roles',len(rb),'sites',len(sites),'unpacked',total,'packed',packed,'saved',total-packed,'slots',len(slots))
for s in slots:print('  %10d'%(s[0]*M),s[1])
