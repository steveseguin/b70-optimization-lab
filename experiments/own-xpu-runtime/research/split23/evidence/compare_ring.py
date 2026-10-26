#!/usr/bin/env python3
"""State gate for OWNRT_QSA_RAW_RING (split23 lab): every buffer of the candidate dump must equal the reference dump
bitwise, except blk.N.qsa.raw, which the candidate holds as a 512-row ring: there every ring slot must equal the newest
reference row with that slot index (rows written: 0 .. positions-1). Prints a driver-compare-like JSON."""
import json,sys,hashlib
from pathlib import Path
RING=512
KVROW=512*4   # F32 keys/values row: 2 KV heads x 256
POOLROW=128*4 # F32 pooled row
def load(root):
    d=Path(root)/'rank1'/'state-2147483647'
    idx={}
    for line in (d/'state-index.tsv').read_text().splitlines()[1:]:
        n,off,ln,sha=line.split('\t');idx[n]=(int(off),int(ln),sha)
    return d,idx,json.loads((d/'state.json').read_text())
def main(a,b,positions):
    da,ia,sa=load(a);db,ib,sb=load(b)
    keys=sorted(set(ia)&set(ib));only=sorted(set(ia)^set(ib));differ=[];ring_checked=[];prefix_checked=[]
    fa=open(da/'state.bundle','rb');fb=open(db/'state.bundle','rb')
    for k in keys:
        if ia[k][1]==ib[k][1]:
            if ia[k][2]!=ib[k][2]:differ.append(k)
            continue
        base=k[:-4] if k.endswith('.bin') else k
        if base.endswith(('.qsa.keys','.qsa.values','.qsa.pooled')):
            # different context capacities (e.g. 32768 vs 65536): the first written rows must match, the rest must be zero
            offa,lna,_=ia[k];offb,lnb,_=ib[k];fa.seek(offa);x=fa.read(lna);fb.seek(offb);y=fb.read(lnb)
            rows_written=(positions//4) if base.endswith('.qsa.pooled') else positions
            per=(KVROW if not base.endswith('.qsa.pooled') else POOLROW)
            n=rows_written*per;short,long_=(x,y) if len(x)<len(y) else (y,x)
            prefix_checked.append(k)
            if x[:n]!=y[:n] or any(long_[n:]) or any(short[n:]):differ.append(k)
            continue
        if not (k.endswith('.qsa.raw') or k.endswith('.qsa.raw.bin')):differ.append(k);continue
        offa,lna,_=ia[k];offb,lnb,_=ib[k];row=POOLROW
        if lna==RING*row and lnb>lna:  # reference ring, candidate full: swap roles
            offa,lna,offb,lnb,fx,fy=offb,lnb,offa,lna,fb,fa
        else: fx,fy=fa,fb
        if lnb!=RING*row or lna%row:differ.append(k);continue
        fx.seek(offa);full=fx.read(lna);fy.seek(offb);ring=fy.read(lnb);bad=0
        for slot in range(RING):
            r=positions-1-((positions-1-slot)%RING)
            want=full[r*row:(r+1)*row] if r>=0 else bytes(row)
            bad+=ring[slot*row:(slot+1)*row]!=want
        ring_checked.append(k)
        if bad:differ.append(k)
    # the state JSON's per-buffer hashes for the raw rings differ by construction; every other field must match
    other={k:(sa[k],sb[k]) for k in sa if k!='buffers' and sa.get(k)!=sb.get(k)}
    print(json.dumps(dict(compared=len(keys),ring_reconstructed=len(ring_checked),kv_prefix_compared=len(prefix_checked),differ=differ[:40],differ_count=len(differ),only_one_side=only[:20],other_fields_differ=other)))
    return 1 if differ or only or other else 0
if __name__=='__main__':sys.exit(main(sys.argv[1],sys.argv[2],int(sys.argv[3])))
