#!/usr/bin/env python3
"""Extract static GEN evidence. Never interprets whole-function counts as dynamic costs."""
import collections,hashlib,json,re,struct,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def instructions(lines):
    out=[]
    for n,line in enumerate(lines):
        s=line.strip()
        if not s or s.startswith('//') or s.endswith(':'):continue
        s=re.sub(r'^\([^)]*\)\s*','',s)
        m=re.match(r'([a-z][^\s]*)\s+(?:\((\d+)\|M(\d+)\))?',s)
        if m:out.append((n+1,m[1],int(m[2] or 1),line))
    return out

def stats(ins):
    ops=collections.Counter(x[1] for x in ins)
    mem=[x for x in ins if x[1].startswith(('load.','store.','send','atomic.'))]
    return dict(instructions=len(ins),simd16_issue_equivalents=sum(max(1,x[2]/16) for x in ins),
       memory_messages=len(mem),messages=dict(collections.Counter(x[1] for x in mem)),
       alu64=sum(bool(re.search(r':u?q\b',x[3])) and not x[1].startswith(('load.','store.','send')) for x in ins),
       conversions_to_float=sum(x[1]=='mov' and bool(re.search(r':f\b',x[3])) and bool(re.search(r':(?:b|ub|w|uw|hf|d|ud)\b',x[3])) for x in ins),
       indirect_register_moves=sum(x[1]=='mov' and 'r[a0' in x[3] for x in ins),
       barriers=sum('barrier' in x[1] or 'barrier' in x[3].lower() for x in ins),
       slm_messages=sum('.slm.' in x[1] for x in ins),
       calls=sum(x[1] in ('call','calla','fcall') for x in ins),
       explicit_scratch_messages=sum('scratch' in x[3].lower() or '.scr.' in x[1] for x in mem),
       instruction_widths=dict(collections.Counter(str(x[2]) for x in ins)))

def parse(f):
    text=f.read_text();lines=text.splitlines();name=lines[0].removeprefix('//.kernel ')
    dem=subprocess.check_output(['c++filt',name],text=True).strip()
    ins=instructions(lines);s=stats(ins)
    labels={line.strip()[:-1]:i+1 for i,line in enumerate(lines) if re.match(r'^_\d+_\d+:$',line.strip())}
    loops=[]
    for n,op,w,line in ins:
        if op not in ('goto','jmpi','while'):continue
        for target in set(re.findall(r'_\d+_\d+',line.split('//')[0])):
            if target in labels and labels[target]<n:
                body=[x for x in ins if labels[target]<=x[0]<=n]
                loops.append(dict(first_line=labels[target],last_line=n,header=target,**stats(body)))
    # Regions are lexical backedge envelopes, including mutually exclusive branches.
    s.update(kernel=name,demangled=dem,asm=str(f.relative_to(P)),asm_sha256=sha(f),
      simd=int(re.search(r'_simd(\d+)_',f.name)[1]),
      grf=int(re.search(r'numGRF=(\d+)',text)[1]),
      spill_metadata=[l for l in lines if l.startswith('//.spill')],
      scratch_note='A32 transposed UGM messages can be spill/fill even without scratch in disassembly. Use spill_metadata and execution_env; text signature alone is incomplete.',
      backward_branch_regions=loops,
      prologue_instructions_before_first_branch=next((i for i,x in enumerate(ins) if x[1] in ('goto','jmpi','if','while')),len(ins)),
      dynamic_instructions_per_weight=None,dynamic_messages_per_weight=None,
      dynamic_limit='Static lexical counts include divergent and exceptional paths. Null dynamic count is unestablished, not zero.')
    z=next(f.parent.glob('*.zeinfo'),None)
    if z:
        zs=z.read_text();a=zs.find('  - name:            '+name+'\n');b=zs.find('  - name:',a+10);zs=zs[a:b if b!=-1 else None] if a!=-1 else ''
        env=zs.split('payload_arguments:')[0]
        s['execution_env']={m[1]:m[2] for m in re.finditer(r'^      (\w+):\s+([^\n]+)',env,re.M)}
        def section(key):
            match=re.search(r'^    '+re.escape(key)+r':\s*\n(.*?)(?=^    [a-z_]+:|^[a-z_]+:|\Z)',zs,re.M|re.S)
            return match[1] if match else ''
        def extent(body):
            pairs=re.findall(r'offset:\s+(\d+)\s+size:\s+(\d+)',body)
            return max((int(a)+int(b) for a,b in pairs),default=0)
        # Per-thread local-ID bytes are a separate address space from cross-thread args.
        s['cross_thread_payload_extent_bytes']=extent(section('payload_arguments'))
        s['per_thread_payload_extent_bytes']=extent(section('per_thread_payload_arguments'))
        s['per_thread_memory_buffers_metadata']=section('per_thread_memory_buffers').splitlines()
    return s

def binary_text_sections(folder):
    # ocloc progbin is an ELF64 object; reading it performs no device access.
    found={}
    for f in sorted(folder.glob('*.progbin')):
        blob=f.read_bytes()
        if blob[:6]!=b'\x7fELF\x02\x01':continue
        h=struct.unpack_from('<16sHHIQQQIHHHHHH',blob)
        sections=[struct.unpack_from('<IIQQQQIIQQ',blob,h[6]+i*h[11]) for i in range(h[12])]
        shstr=sections[h[13]];names=blob[shstr[4]:shstr[4]+shstr[5]]
        for section in sections:
            name=names[section[0]:].split(b'\0')[0].decode()
            if name.startswith('.text.'):
                found[name[6:]]=(f,blob[section[4]:section[4]+section[5]])
    return found

def main():
    rows=[];rejected=[]
    active={r['dump'] for r in json.loads((P/'candidate-modules.json').read_text())} if (P/'candidate-modules.json').exists() else set()
    for folder in sorted((P/'build').glob('igc-*')):
        if folder.name=='igc-down' or (folder.name.startswith('igc-p33-') and str(folder.relative_to(P)) not in active):continue
        binary_sections=binary_text_sections(folder)
        attempts=[]
        for f in sorted(folder.glob('*entry_*.asm')):
            r=parse(f)
            if 'Intel_Symbol_Table' in r['kernel']:continue
            pair=binary_sections.get(r['kernel']);dat=f.with_suffix('.dat')
            if pair and dat.exists():
                binary,body=pair;encoded=dat.read_bytes()
                match=body.startswith(encoded) and not any(body[len(encoded):])
                r['offline_binary_match']=dict(selected=match,binary=str(binary.relative_to(P)),binary_sha256=sha(binary),
                    binary_text_sha256=hashlib.sha256(body).hexdigest(),text_bytes=len(body),dat_sha256=sha(dat),dat_bytes=len(encoded),
                    proof='Entire GEN .dat equals ELF .text prefix and remaining padding is all zero.' if match else 'GEN .dat does not match final ELF .text; discarded IGC compile attempt.')
            else:r['offline_binary_match']=dict(selected=None,proof='Missing .dat or matching ELF text section; not proven.')
            attempts.append(r)
        for r in attempts:
            (rejected if r['offline_binary_match']['selected'] is False else rows).append(r)
    data=dict(schema='packet33.codegen.v1',device_executed=False,scope='offline GEN for exact shipped SPIR-V; runtime equivalence limitations in runtime-options.md',kernels=rows,rejected_compile_attempts=rejected)
    (P/'codegen.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(len(rows),'kernels;',len(rejected),'rejected compile attempts')
if __name__=='__main__': main()
