#!/usr/bin/env python3
"""Compile new kernels offline for BMG-G31; never opens a GPU device."""
import gzip, json, os, re, subprocess, time
from pathlib import Path
from preparation import exclusive_cpu_work
from window_support import HERE, REPO, sha, save, require

def main():
    with exclusive_cpu_work(200_000_000):
        out=HERE/'build'/('registers-'+str(time.time_ns()));out.mkdir(exist_ok=False)
        evidence=HERE/'evidence-cpu/registers';evidence.mkdir(parents=True,exist_ok=True)
        compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx')
        translator=compiler.parent/'compiler/llvm-spirv'
        flags=['-fsycl','-fsycl-device-only','-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
        for d in (HERE.parent/'packet45-merged3',HERE.parent.parent/'stage1/packet3-prep/src',HERE.parent/'packet2/kernels',HERE.parent/'packet2/loader'):
            flags.extend(['-I',str(d)])
        from window_support import verify_files
        build=json.loads((HERE/'build-device.json').read_text())
        verify_files(build['source_hashes'],REPO);verify_files(build['artifacts'],REPO)
        source=out/'inspect_kernels.cpp'
        source.write_text((HERE/'inspect_kernels.cpp').read_text().replace('"dense_virtual.hpp"',json.dumps(str(HERE/'build/device/source/dense_virtual.hpp'))))
        commands=[ [str(compiler),*flags,'-c',str(source),'-o',str(out/'kernels.bc')],
            [str(translator),'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers',str(out/'kernels.bc'),'-o',str(out/'kernels.spv')],
            ['/usr/bin/ocloc','compile','-spirv_input','-file',str(out/'kernels.spv'),'-device','bmg-g31','-out_dir',str(out/'aot')]]
        env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out/'igc'),'IGC_ShowFullVectorsInShaderDumps':'1'}
        for i,cmd in enumerate(commands):
            with (evidence/f'compile-{i}.log').open('w') as log:
                result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1200)
            require(result.returncode==0,'offline compile failed: '+str(evidence))
        kernels=[]
        for i,p in enumerate(sorted((out/'igc').glob('*entry_*.asm'))):
            data=p.read_text()
            if 'p53b' not in data.splitlines()[0] and 'p51' not in data.splitlines()[0]:continue
            artifact=evidence/f'kernel-{i}.asm.gz';artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
            grf=re.search(r'numGRF=(\d+)',data)
            kernels.append(dict(name=data.splitlines()[0],configured_grf=int(grf[1]) if grf else None,
                spill_metadata=[l for l in data.splitlines()[:40] if l.startswith('//.spill')],
                scratch_memory_messages=[l for l in data.splitlines() if 'scratch' in l.lower() and not l.lstrip().startswith('//')],
                artifact=str(artifact.relative_to(REPO)),sha256=sha(artifact)))
        require(len(kernels)==15,'expected 6 expert + 6 HC + 2 small kernels + HC low control, got '+str(len(kernels)))
        large_gate=[k for k in kernels if 'TypeE22E' in k['name'] and 'submit_stream_arm' in k['name']]
        require(len(large_gate)==2 and all(not k['spill_metadata'] for k in large_gate),'V8/V16 gate replacement must have zero spills')
        save(HERE/'register-report.json' ,dict(schema='ownrt.packet53b.registers.v1',passed=True,device_executed=False,
            scope='Offline BMG-G31 native compilation of identical new kernel templates with device-build math flags; not installed-driver JIT capture',
            commands=commands,environment={k:v for k,v in env.items() if k.startswith('IGC_')},kernels=kernels,
            tools={str(p):sha(p) for p in (compiler,translator,Path('/usr/bin/ocloc'))},
            build_device_sha256=sha(HERE/'build-device.json'),sources={str((HERE/n).relative_to(REPO)):sha(HERE/n) for n in ('inspect_kernels.cpp','inspect_registers.py','expert_order.hpp','dense_virtual.hpp','production_gemv.hpp')},
            logs={str(p.relative_to(REPO)):sha(p) for p in evidence.glob('*.log')}))
        print(json.dumps(kernels,indent=2))
if __name__=='__main__':main()
