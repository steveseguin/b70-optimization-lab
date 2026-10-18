"""Check linked vISA and final BMG sends, including their scoreboard waits.

IQ2 grid words are the d32x2 loads first consumed by an eight-bit magnitude
mask. Resolve vISA aliases before finding that first consumer. Bind each
instruction ID to final assembly; no earlier destination wait may serialize
one batch. This is a static issue-order proof, never a speed measurement.
"""
import gzip,json,re
from collections import defaultdict
from build_engine import P,ROOT,sha,save,limits

def inspect(visa,assembly,batch,shared):
    lines=visa.splitlines();asm=assembly.splitlines();aliases={}
    for line in lines:
        match=re.match(r'\.decl (V\d+).* alias=<(V\d+),',line)
        if match:aliases[match[1]]=match[2]
    def root(v):
        while v in aliases:v=aliases[v]
        return v
    def identity(line):
        return int(re.search(r'\$(\d+)\s*$',line)[1])
    def hardware(number,kind):
        found=[(i,line) for i,line in enumerate(asm) if re.search(r'\$'+str(number)+r'(?:\s|$)',line) and kind in line and not line.lstrip().startswith('//')]
        assert len(found)==1,(number,kind,found)
        return found[0]
    grids=[];input_groups=defaultdict(set)
    for i,line in enumerate(lines):
        activation=re.search(r'lsc_load\.ugm .* V\d+:d32  flat\[(V\d+)(\+0x[0-9a-f]+)?\]:a64',line)
        if activation:input_groups[root(activation[1])].add(int(activation[2][1:],16) if activation[2] else 0)
        match=re.search(r'lsc_load\.ugm .* (V\d+):d32x2  flat\[',line)
        if not match:continue
        target=root(match[1]);consumer=None
        for j in range(i+1,len(lines)):
            text=lines[j]
            if text.lstrip().startswith(('.', '//')):continue
            if any(root(v)==target for v in re.findall(r'\bV\d+\b',text)):
                consumer=(j,text);break
        assert consumer is not None
        j,text=consumer
        if not re.match(r'\s*and ',text) or not re.search(r' 0xff:',text):continue
        send,send_text=hardware(identity(line),'load.ugm.d32x2.a64')
        consume,consume_text=hardware(identity(text),'and ')
        scoreboard=re.search(r'\$(\d+)\}',send_text)
        assert scoreboard,send_text
        grids.append(dict(visa_send_line=i+1,visa_first_consumer_line=j+1,
            send_id=identity(line),consumer_id=identity(text),asm_send_line=send+1,
            asm_first_consumer_line=consume+1,scoreboard=int(scoreboard[1]),
            send=send_text.strip(),consumer=consume_text.strip()))
    assert len(grids)==8,('expected eight independent grid words per step',len(grids))
    width=batch*(2 if shared else 1);groups=[]
    for start in range(0,len(grids),width):
        group=grids[start:start+width]
        assert max(r['visa_send_line'] for r in group)<min(r['visa_first_consumer_line'] for r in group),'vISA consumes before batch issue'
        last=max(r['asm_send_line'] for r in group)
        assert last<min(r['asm_first_consumer_line'] for r in group),'hardware consumes before batch issue'
        for row in group:
            between=asm[row['asm_send_line']:last-1]
            assert not any(re.search(r'\$'+str(row['scoreboard'])+r'\.dst\b',line) or 'sync.allrd' in line for line in between),'early grid destination wait'
        groups.append(dict(passed=True,independent_sends=len(group),last_send_line=last,
            first_consumer_line=min(r['asm_first_consumer_line'] for r in group),no_early_destination_wait=True,loads=group))
    vectors=sum(offsets=={0,4,8,12} for offsets in input_groups.values())
    assert vectors==(4 if shared else 8),('activation groups',vectors,input_groups)
    return dict(passed=True,grid_words_per_step=8,batch_grid_words=width,
        activation_vectors_per_step=vectors,activation_d32_loads_per_step=vectors*4,groups=groups)

def main():
    limits();report=json.loads((P/'register-report-offline.json').read_text());rows=[]
    sources={str((P/'lookup_proof.py').relative_to(ROOT)):sha(P/'lookup_proof.py'),
             str((P/'register-report-offline.json').relative_to(ROOT)):sha(P/'register-report-offline.json')}
    for row in report['kernels']:
        if row['rejected']:continue
        name=row['name'];batch,shared=(1,False)
        if 'p102' in name:
            match=re.search(r'KernelILj(\d+)ELb([01])',name);batch=int(match[1]);shared=match[2]=='1'
        v=ROOT/row['visa'];a=ROOT/row['assembly'];assert sha(v)==row['visa_sha256'] and sha(a)==row['sha256']
        result=inspect(gzip.decompress(v.read_bytes()).decode(),gzip.decompress(a.read_bytes()).decode(),batch,shared)
        sources[str(v.relative_to(ROOT))]=sha(v);sources[str(a.relative_to(ROOT))]=sha(a)
        rows.append(dict(name=name,batch=batch,shared=shared,visa=row['visa'],assembly=row['assembly'],**result))
    assert len(rows)==4
    save(P/'evidence/lookup-issue-proof.json',dict(passed=True,device_executed=False,sources=sources,kernels=rows,
         scope='linked offline BMG-G31 send ordering and activation-load reuse; device speed remains pending'))
    print('Four linked kernels: independent sends before consumption, no early wait; shared activation reads halved')
if __name__=='__main__':main()
