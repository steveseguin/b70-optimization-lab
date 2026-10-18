"""Compile-only, separately linked expert images with linked spill evidence."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import shutil
import subprocess
from build_engine import P,limits
from compile_turn import turn

ROOT=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    limits();b=P/'build';e=P/'evidence';(b/'tmp').mkdir(exist_ok=True)
    compiler='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
    from mirror import prepare
    source=prepare(P/'expert_image.cpp')
    flags=['-I'+str(P.parent/'packet103-record-bundle'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl','-fsycl-targets=spir64_gen','-fsycl-device-code-split=per_source','-fPIC','-shared','-Werror=deprecated-this-capture']
    rows=[]
    for mode in ('normal','large'):
        limits();out=b/f'igc-{mode}'
        if out.exists():shutil.rmtree(out)
        out.mkdir()
        options='-ze-fp32-correctly-rounded-divide-sqrt -ze-opt-print-spill'+(' -ze-opt-large-register-file' if mode=='large' else '')
        cmd=[compiler,*flags,'-Xs',f'-device bmg-g31 -options "{options}"',*(['-DP115_NORMAL'] if mode=='normal' else []),'-MMD','-MF',str(b/f'{mode}.d'),str(source),'-o',str(b/f'libp115_{mode}.so')]
        env={**os.environ,'TMPDIR':str(b/'tmp'),'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out),'IGC_ShowFullVectorsInShaderDumps':'1'}
        with turn(),(e/f'build-{mode}.log').open('w') as log:
            r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,timeout=600)
        print(mode,r.returncode,(e/f'build-{mode}.log').read_text()[-2500:],flush=True)
        row=dict(mode=mode,command=cmd,returncode=r.returncode,kernels=[])
        rows.append(row)
        if r.returncode:break
        zeinfos=list(out.glob('*.zeinfo'));assert len(zeinfos)==1
        zi=zeinfos[0].read_text().split('\nkernels_misc_info:')[0]
        blocks=re.split(r'\n  - name:\s*',zi)[1:]
        metadata={block.splitlines()[0].strip():block for block in blocks}
        zi_saved=e/f'{mode}.zeinfo.gz';zi_saved.write_bytes(gzip.compress(zeinfos[0].read_bytes(),mtime=0))
        row['zeinfo']=dict(path=str(zi_saved.relative_to(P)),sha256=sha(zi_saved))
        for i,f in enumerate(sorted(out.glob('*entry_*.asm'))):
            s=f.read_text();grf=re.search(r'numGRF=(\d+)',s);meta=[l for l in s.splitlines() if l.startswith('//.spill')]
            scratch=[l for l in s.splitlines() if not l.lstrip().startswith('//') and any(x in l.lower() for x in ('scratch','spill to','fill from'))]
            block=metadata[s.splitlines()[0].removeprefix('//.kernel ')]
            # Zebin omits per-thread memory buffers for a zero-scratch kernel.
            # Refuse any such allocation, including private/stack buffers.
            per_thread=bool(re.search(r'per_thread_memory_buffers|scratch_size|spill_size|private_size',block))
            saved=e/f'{mode}-kernel-{i}.asm.gz';saved.write_bytes(gzip.compress(f.read_bytes(),mtime=0))
            row['kernels'].append(dict(name=s.splitlines()[0],grf=int(grf[1]) if grf else None,spill_metadata=meta,scratch_messages=len(scratch),per_thread_memory_allocated=per_thread,scratch_bytes=0 if not per_thread else None,spill_free=not per_thread and all(re.search(r'[: ]0$',x.strip()) for x in meta) and not scratch,assembly=str(saved.relative_to(P)),sha256=sha(saved)))
        deps=shlex.split((b/f'{mode}.d').read_text().replace('\\\n',' ').split(':',1)[1])
        row['sources']={str(Path(p).resolve().relative_to(ROOT)):sha(p) for p in deps if Path(p).resolve().is_relative_to(ROOT)}
        for path in list(row['sources']):
            f=ROOT/path
            if f.is_relative_to(b/'checked'):
                original=ROOT/f.relative_to(b/'checked')
                row['sources'][str(original.relative_to(ROOT))]=sha(original)
        for f in (P/'build_images.py',P/'mirror.py',P.parent/'packet103-record-bundle/submission_overlay.py'):
            row['sources'][str(f.relative_to(ROOT))]=sha(f)
        row['artifact']={str((b/f'libp115_{mode}.so').relative_to(P)):sha(b/f'libp115_{mode}.so')}
    passed=len(rows)==2 and all(r['returncode']==0 and r['kernels'] and all(k['spill_free'] and k['grf']==(256 if r['mode']=='large' else 128) for k in r['kernels']) for r in rows)
    report=dict(schema='packet115.expert-images.v1',passed=passed,device_executed=False,images=rows,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (e/'images.json').write_text(json.dumps(report,indent=2)+'\n')
    print([(r['mode'],[(k['grf'],k['spill_free']) for k in r['kernels']]) for r in rows],flush=True)

if __name__=='__main__':main()
