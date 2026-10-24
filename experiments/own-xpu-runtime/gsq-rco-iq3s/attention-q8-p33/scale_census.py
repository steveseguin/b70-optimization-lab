#!/usr/bin/env python3
"""One bounded read of only the48 admitted Q8 tensors; no model execution."""
import collections,hashlib,json,os,resource,stat,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
    if not v:raise ValueError(m)
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read(fd,n,off):
    out=os.pread(fd,n,off);require(len(out)==n,'short admitted read');return out
def main():
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    pins=json.loads((P/'control-pins.json').read_text());cpath=L/'metadata/new-census.json';require(sha(cpath)==pins[str(cpath)],'census source changed')
    census=json.loads(cpath.read_text());prep=json.loads((P/'preparation.json').read_text());fds={};out=[];start=time.monotonic();read_bytes=0
    try:
        for s in census['shards']:
            path=Path(s['path']);require(path.parent.resolve()==Path(census['root']) and not path.is_symlink(),'canonical admitted shard')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fds[path.name]=(fd,s)
            require(stat.S_ISREG(os.fstat(fd).st_mode) and identity(os.fstat(fd))==s['stat_identity'],'held shard identity')
            raw=read(fd,s['header_bytes_read'],0);read_bytes+=len(raw)
            require(hashlib.sha256(raw).hexdigest()==s['header_sha256'],'exact authenticated header prefix')
        for selected in prep['sites']:
            t=census['tensors'][selected['weight']];require(t['type']=='Q8_0' and t['shape']==[2560,6144] and t['bytes']==16711680,'fixed tensor geometry')
            fd,s=fds[t['shard']];counts=collections.Counter();digest=hashlib.sha256();off=t['file_offset'];end=off+t['bytes']
            require(off>=s['data_start'] and end<=s['file_bytes'],'admitted payload bounds')
            for begin in range(off,end,34*32768):
                raw=read(fd,min(34*32768,end-begin),begin);read_bytes+=len(raw);digest.update(raw)
                require(len(raw)%34==0,'whole Q8 blocks');counts.update(a|(b<<8) for a,b in zip(raw[0::34],raw[1::34]))
            categories=dict(normal=0,subnormal=0,positive_zero=0,negative_zero=0,infinity=0,nan=0)
            for h,n in counts.items():
                exponent=h&0x7c00;fraction=h&0x3ff
                key=('nan' if fraction else 'infinity') if exponent==0x7c00 else ('subnormal' if fraction else 'negative_zero' if h&0x8000 else 'positive_zero') if not exponent else 'normal'
                categories[key]+=n
            require(sum(categories.values())==2560*192,'every scale counted')
            out.append(dict(weight=selected['weight'],file_offset=off,bytes=t['bytes'],payload_sha256=digest.hexdigest(),scale_words=sum(categories.values()),categories=categories,distinct_half_patterns=len(counts)))
            require(identity(os.fstat(fd))==s['stat_identity'],'shard mutated during tensor scan')
        for fd,s in fds.values():require(identity(os.fstat(fd))==s['stat_identity'] and identity(os.stat(s['path'],follow_symlinks=False))==s['stat_identity'],'held/path shard identity changed')
        totals={k:sum(r['categories'][k] for r in out) for k in out[0]['categories']}
        require(len(out)==48 and read_bytes==802160640+11024355+173,'exact bounded read budget')
        result=dict(passed=True,all_scales_finite=totals['nan']==totals['infinity']==0,totals=totals,tensors=out,read_bytes=read_bytes,header_identity_sha256=sha(cpath),preparation_sha256=sha(P/'preparation.json'),source_sha256=sha(__file__),elapsed_seconds=time.monotonic()-start,device_execution=False,full_model_payload_read=False)
        dest=P/'evidence/scale-census.json';dest.parent.mkdir(exist_ok=True)
        with dest.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps({'passed':True,'all_scales_finite':result['all_scales_finite'],'read_bytes':read_bytes,'totals':totals,'receipt_sha256':sha(dest)}))
    finally:
        for fd,s in fds.values():os.close(fd)
if __name__=='__main__':main()
