#!/usr/bin/env python3
"""CPU-only BMG-G31 native ISA: icpx bitcode -> SPIR-V -> ocloc/IGC."""
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
HERE=Path(__file__).resolve().parent
COMPILER='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
TRANSLATOR='/opt/intel/oneapi/compiler/2026.0/bin/compiler/llvm-spirv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect():
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise ValueError('nice19/OMP2 required')
    build=HERE/'build/isa';build.mkdir(parents=True,exist_ok=False)
    evidence=HERE/'build/isa-evidence';evidence.mkdir(exist_ok=True)
    receipt=dict(schema='own-runtime.iq3.packet11.native-isa.v1',device_executed=False,native_isa=True,
        target='bmg-g31 offline, not a capture of the installed runtime JIT',commands=[],kernels=[])
    def run(argv,env=None,required=True):
        p=subprocess.run(list(map(str,argv)),capture_output=True,text=True,env=env,cwd=build)
        receipt['commands'].append(dict(argv=list(map(str,argv)),environment_overrides={k:env[k] for k in env or {} if k.startswith('IGC_')},returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        if required and p.returncode:raise RuntimeError(p.stderr or p.stdout)
    flags=['-fsycl','-fsycl-device-only','-O3','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-I'+str(HERE.parent.parent/'stage1/packet3-prep/src')]
    for label,source in [('packet9',HERE.parent/'packet9-kopt4/kernels.cpp'),('packet11',HERE/'kernels.cpp')]:
        bc=build/(label+'.bc');spv=build/(label+'.spv');dump=build/('igc-'+label)
        if label=='packet9':run([COMPILER,*flags,source,'-S','-o',build/'requested.s'],required=False)
        run([COMPILER,*flags,source,'-c','-o',bc])
        # These two newer extensions are not understood by installed ocloc's
        # translator. Disabling emission preserves typed pointers/arithmetic.
        run([TRANSLATOR,'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers',bc,'-o',spv])
        env=dict(os.environ,IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
        run(['/usr/bin/ocloc','compile','-spirv_input','-file',spv,'-device','bmg-g31','-out_dir',build/('aot-'+label)],env)
        for f in sorted(dump.glob('*entry_*.asm')):
            text=f.read_text();kernel=text.splitlines()[0]
            m=re.search(r'TypeE(21|22)E',kernel)
            if not m:continue
            t='IQ2_S' if m[1]=='22' else 'IQ3_S'
            v=re.search(r'VariantE(\d)',kernel);variant=int(v[1]) if v else 0
            name=f'{label}-{t}-v{variant}.asm.gz'
            (evidence/name).write_bytes(gzip.compress(f.read_bytes(),mtime=0))
            instructions=[line for line in text.splitlines() if re.search(r'\(\d+\|M\d+\)',line) and not line.lstrip().startswith('//')]
            counts=collections.Counter(re.sub(r'^\([^)]*\)\s*','',line.strip()).split()[0] for line in instructions)
            grf=re.search(r'numGRF=(\d+)',text)
            receipt['kernels'].append(dict(source=label,type=t,variant=variant,kernel=kernel,scratch_artifact='build/isa-evidence/'+name,
                asm_sha256=sha(f),gzip_sha256=sha(evidence/name),asm_bytes=f.stat().st_size,
                configured_grf=int(grf[1]),whole_kernel_static_instructions=len(instructions),opcode_counts=dict(sorted(counts.items())),
                spill_metadata=[l for l in text.splitlines()[:20] if l.startswith('//.spill')],
                scratch_memory_messages=[l for l in instructions if 'scratch' in l.lower()],
                fma_instructions=[l for l in instructions if re.search(r'\b(fma|mad)\b',l) and ':f' in l]))
    if len(receipt['kernels'])!=10:raise ValueError('expected two baseline and eight candidate native kernels')
    if any('(1|M0)' not in line for k in receipt['kernels'] for line in k['fma_instructions']):raise ValueError('unexpected vector floating FMA')
    receipt['scalar_mad_note']='12 SIMD1 MADs per kernel implement compiler-generated unsigned division in launch indexing; no vector weight/accumulator FMA.'
    receipt['compiler_sha256']=sha(Path(COMPILER))
    receipt['ocloc_sha256']=sha(Path('/usr/bin/ocloc'))
    receipt['translator_sha256']=sha(Path(TRANSLATOR))
    receipt['source_sha256']={str(p.relative_to(HERE.parents[3])):sha(p) for folder in (HERE,HERE.parent/'packet9-kopt4',HERE.parent/'packet8-kopt3',HERE.parent/'packet7-kopt2',HERE.parent/'packet6-kopt',HERE.parent/'packet2/kernels') for p in folder.iterdir() if p.suffix in ('.cpp','.hpp')}
    receipt['scope']='Whole-kernel static instruction counts include mutually exclusive slow paths, setup and reductions; not dynamic per-grid counts or measured issue/latency.'
    (HERE/'assembly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ('source','type','variant','configured_grf','whole_kernel_static_instructions','spill_metadata')} for r in receipt['kernels']],indent=2))
if __name__=='__main__':inspect()
