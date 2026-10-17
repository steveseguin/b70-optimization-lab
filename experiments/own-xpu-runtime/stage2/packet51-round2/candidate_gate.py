#!/usr/bin/env python3
"""Serial, device-free operator checks under GNU, Intel and ASan/UBSan."""
import json
import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from preparation import exclusive_cpu_work
from window_support import sha, verify_files
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def run():
    result=dict(schema='ownrt.packet51.candidate-gates.v1',passed=False,device_executed=False)
    with exclusive_cpu_work(200_000_000):
        build=json.loads((HERE/'build-layer-host.json').read_text())
        assert build.get('passed') is True and build.get('mode')=='host' and build.get('device_executed') is False
        verify_files(build['source_hashes'],ROOT);verify_files(build['artifacts'],ROOT)
        sources=dict(build['source_hashes']);sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
        sources.update({str(f.relative_to(ROOT)):sha(f) for f in (HERE/'build/host/source').glob('*') if f.is_file()})
        out=HERE/'evidence-cpu'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');out.mkdir(parents=True,exist_ok=False)
        env=dict(os.environ,OMP_NUM_THREADS='2',ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
        original=HERE/'build/host/candidate-cpu-test'
        source=HERE/'build/host/source/candidate_cpu_test.cpp'
        common=['-std=c++20','-O2','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-fopenmp']
        commands=[];runs=[];compilers={};artifacts={str(original.relative_to(ROOT)):sha(original)}
        for label,compiler,flags in [('gnu',None,[]),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx',['-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']),('asan','/usr/bin/g++',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
            binary=original if compiler is None else HERE/'build'/('candidate-'+label)
            actual_compiler=compiler or '/usr/bin/g++'
            compilers[label]=dict(path=actual_compiler,sha256=sha(actual_compiler),version=subprocess.run([actual_compiler,'--version'],text=True,capture_output=True,check=True).stdout)
            if compiler:
                cmd=[compiler,*common,*flags,str(source),'-lcrypto','-o',str(binary)]
                commands.append(cmd)
                with (out/(label+'-compile.log')).open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,env=env)
                artifacts[str(binary.relative_to(ROOT))]=sha(binary)
            for repeat in range(1,2 if label=='asan' else 3):
                run=subprocess.run([str(binary)],env=env,text=True,capture_output=True,timeout=600)
                name=label+'-'+str(repeat)
                (out/(name+'.log')).write_text(run.stdout+run.stderr)
                if run.returncode:raise RuntimeError(name+' failed; retained log')
                row=json.loads(run.stdout)
                if row.get('passed') is not True or row.get('device_executed') is not False or row.get('checks',0)<=0:raise ValueError(name+' incomplete')
                runs.append(dict(compiler=label,repeat=repeat,receipt=row,log=str((out/(name+'.log')).relative_to(ROOT)),log_sha256=sha(out/(name+'.log'))))
        assert len({r['receipt']['checks'] for r in runs})==1, 'check count differs'
        # The unchanged repacker rejects every nonfinite weight scale. Their
        # direct-decoder diagnostics remain exact to the same-compiler oracle,
        # but its NaN payload differs between compilers (retained phase evidence).
        excluded={'weight_half_31744','weight_half_64512','weight_half_32257'}
        finite_halves=(0,32768,1,32769,1023,1024,15360,48128,31743,64511)
        supported={'codebook_all_signs_finite_scale','gate','route','hc_gate','hc_low',
                   'hc_inject_diagnostic','attention','qkv','repack_reject_all_nonfinite_encodings'}
        supported.update('weight_half_'+str(h) for h in finite_halves)
        for r in runs:
            phases=r['receipt']['phase_sha256']
            assert set(phases)==supported|excluded, 'incomplete or foreign phase census'
            assert all(isinstance(h,str) and len(h)==64 and set(h)<=set('0123456789abcdef') for h in [*phases.values(),r['receipt']['output_sha256']]), 'malformed digest'
            r['supported_phase_sha256']={name:phases[name] for name in sorted(supported)}
        assert all(r['supported_phase_sha256']==runs[0]['supported_phase_sha256'] for r in runs), 'admitted-domain compiler byte identity differs'
        for compiler in ('gnu','intel','asan'):
            assert len({r['receipt']['output_sha256'] for r in runs if r['compiler']==compiler})==1, 'same-compiler full diagnostic repeat differs'
        supported_digest=hashlib.sha256(json.dumps(runs[0]['supported_phase_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        verify_files(sources,ROOT);verify_files(artifacts,ROOT)
        result.update(passed=True,source_hashes=sources,artifacts=artifacts,commands=commands,compilers=compilers,runs=runs,
                      supported_phase_manifest_sha256=supported_digest,
                      unsupported_weight_phases=sorted(excluded),
                      all_diagnostic_bytes_match_across_compilers=len({r['receipt']['output_sha256'] for r in runs})==1,build_receipt_sha256=sha(HERE/'build-layer-host.json'))
        (HERE/'cpu-candidate-gates.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,device_executed=False,runs=len(runs),checks=[r['receipt']['checks'] for r in runs])))
def main():
    try:run()
    except Exception as error:
        (HERE/'cpu-candidate-gates.json').write_text(json.dumps(dict(passed=False,device_executed=False,error=str(error)),indent=2)+'\n')
        raise
if __name__=='__main__':main()
