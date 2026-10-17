#!/usr/bin/env python3
"""Serial, bounded M1/M2 small proofs and one full-shape M1 composition gate."""
import json
import os
import subprocess
import time
from preparation import exclusive_cpu_work
from summarize import CLASSES, CLASS_VARIANTS
from window_support import HERE, REPO, require, sha, save, verify_files


def proof_receipt(path):
    lines=path.read_text().splitlines()
    allowed={
        'OMP: Warning #96: Cannot form a team with 2 threads, using 1 instead.',
        'OMP: Hint Consider unsetting KMP_DEVICE_THREAD_LIMIT (KMP_ALL_THREADS), KMP_TEAMS_THREAD_LIMIT, and OMP_THREAD_LIMIT (if any are set).',
    }
    require(bool(lines) and all(line in allowed for line in lines[:-1]), 'unexpected CPU proof diagnostic')
    return json.loads(lines[-1])


def main():
    with exclusive_cpu_work(8_000_000) as admission:
        save(HERE/'cpu-gates.json', dict(passed=False, device_executed=False, status='in progress'))
        builds = {}
        artifacts = {}
        for mode in ('host','intel-host'):
            row = json.loads((HERE/f'build-{mode}.json').read_text())
            require(row.get('passed') is True and row.get('device_executed') is False and row.get('mode') == mode, 'host build required')
            verify_files(row['source_hashes'], REPO); verify_files(row['artifacts'], REPO)
            expected = {str((HERE/'build'/mode/n).relative_to(REPO)):sha(HERE/'build'/mode/n)
                        for n in ('virtual-bench','cpu-identity-test')}
            require(row['artifacts'] == expected, 'host binaries differ')
            artifacts.update(expected); builds[mode] = row
        stamp=str(time.time_ns()); runs=[]; full_runs=[]
        env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1'}
        for mode in ('host','intel-host'):
            for repeat in range(1):
                out=HERE/'evidence-cpu'/f'{mode}-{stamp}-{repeat}';out.mkdir(parents=True)
                command=[str(HERE/'build'/mode/'cpu-identity-test')]
                start=time.monotonic()
                with (out/'native.log').open('w') as log:
                    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600)
                require(result.returncode == 0,'CPU proof failed; retain '+str(out))
                row=proof_receipt(out/'native.log')
                require(row.get('schema') == 'ownrt.packet53b.cpu_identity.v1' and row.get('passed') is True
                        and row.get('device_executed') is False and row.get('checks',0)>100_000
                        and row.get('rows_checked',0)>0 and len(row.get('output_sha256',''))==64,'CPU proof incomplete')
                save(out/'receipt.json',row)
                runs.append(dict(compiler=mode,repeat=repeat,command=command,checks=row['checks'],rows_checked=row['rows_checked'],
                    elapsed_seconds=time.monotonic()-start,output_sha256=row['output_sha256'],
                    comparisons_sha256=sha(out/'receipt.json'),files={str(p.relative_to(REPO)):sha(p) for p in out.iterdir()}))
        require(len({r['comparisons_sha256'] for r in runs}) == 1,'fresh/cross-compiler CPU proof differs')
        spec=json.loads((HERE/'manifest.json').read_text())
        expected_cases={(c,v,m,t,f) for c in CLASSES for v in ('control',*CLASS_VARIANTS[c])
                        for m in (1,) for t in range(m) for f in range(1)}
        for repeat in range(1):
            out=HERE/'evidence-cpu'/f'full-host-{stamp}-{repeat}';out.mkdir(parents=True)
            command=[str(HERE/'build/host/virtual-bench'),'--mode','cpu-full','--output',str(out)]
            start=time.monotonic()
            with (out/'native.log').open('w') as log:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600)
            require(result.returncode==0,'full CPU harness failed; retain '+str(out))
            receipt=json.loads((out/'receipt.json').read_text())
            require(receipt.get('passed') is True and receipt.get('mode')=='cpu-full'
                    and receipt.get('device_executed') is False and receipt.get('safe_to_exit') is True,'full CPU gate failed')
            rows=[json.loads(s) for s in (out/'comparisons.jsonl').read_text().splitlines()]
            observed={(r['class'],r['variant'],r['m'],r['token_row'],r['iteration']):r for r in rows}
            require(set(observed)==expected_cases and len(rows)==len(expected_cases)==receipt['checks'],'full CPU census differs')
            for key,r in observed.items():
                c,v,m,t,f=key;control=observed[c,'control',m,t,f]
                require(r.get('equal') is True and r.get('production_equal') is True
                        and r['sha256']==r.get('cpu_sha256')==r.get('production_sha256')==control['sha256']
                        and r.get('bytes')==spec['expected_bytes'][c] and r.get('buffers')==spec['expected_buffers'][c],
                        'full production equality/capture differs')
            full_runs.append(dict(repeat=repeat,command=command,elapsed_seconds=time.monotonic()-start,
                checks=len(rows),comparisons_sha256=sha(out/'comparisons.jsonl'),
                files={str(p.relative_to(REPO)):sha(p) for p in out.iterdir()}))
        require(len({r['comparisons_sha256'] for r in full_runs})==1,'fresh full CPU bytes differ')
        # One serial sanitizer run targets the new stride/route/padded indexing.
        # Compile the same checked source mirror as the successful GNU build.
        san_dir=HERE/'build/sanitizer';san_dir.mkdir(exist_ok=True)
        san_out=HERE/'evidence-cpu'/f'sanitizer-{stamp}';san_out.mkdir(parents=True)
        san_binary=san_dir/'cpu-identity-test'
        command=['/usr/bin/g++','-std=c++20','-O1','-g1','-fno-omit-frame-pointer',
                 '-fsanitize=address,undefined','-fno-fast-math','-ffp-contract=off',
                 '-fopenmp','-DOWN_RT_HOST_ONLY','-Werror=return-type']
        for directory in (HERE.parent/'packet45-merged3',HERE.parent.parent/'stage1/packet3-prep/src',
                          HERE.parent/'packet2/kernels',HERE.parent/'packet2/loader'):
            command.extend(['-I',str(directory)])
        command.extend([str(HERE/'build/host/source/cpu_identity_test.cpp'),'-lcrypto','-o',str(san_binary)])
        from preparation import limits
        limits(80_000_000)
        with (san_out/'compile.log').open('w') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600)
        require(result.returncode==0,'sanitizer compile failed; retain '+str(san_out))
        start=time.monotonic()
        with (san_out/'native.log').open('w') as log:
            result=subprocess.run([str(san_binary)],stdout=log,stderr=subprocess.STDOUT,
                env={**env,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'},timeout=600)
        require(result.returncode==0,'sanitizer proof failed; retain '+str(san_out))
        san_row=proof_receipt(san_out/'native.log')
        require(san_row.get('passed') is True and san_row.get('output_sha256')==runs[0]['output_sha256']
                and san_row.get('checks')==runs[0]['checks'],'sanitizer proof output differs')
        sanitizer=dict(passed=True,device_executed=False,command=command,elapsed_seconds=time.monotonic()-start,
                       checks=san_row['checks'],output_sha256=san_row['output_sha256'],
                       files={str(p.relative_to(REPO)):sha(p) for p in san_out.iterdir()})
        artifacts[str(san_binary.relative_to(REPO))]=sha(san_binary)
        sources={str((HERE/n).relative_to(REPO)):sha(HERE/n) for n in ('cpu_gate.py','manifest.json','cpu_identity_test.cpp','expert_order.hpp','dense_virtual.hpp','bench.cpp')}
        row=dict(schema='own-runtime.packet53b.cpu-gates.v1',passed=True,device_executed=False,
            build_receipt_sha256=sha(HERE/'build-host.json'),intel_build_receipt_sha256=sha(HERE/'build-intel-host.json'),
            artifacts=artifacts,sources=sources,admission=admission,runs=runs,full_runs=full_runs,sanitizer=sanitizer,
            environment={'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1'},
            scope='independent FP32 chains/tree, decode, scheduling, controls; one complete production-shape M1 host pass; M2 small proofs; full device M1/M2 equality pending')
        save(HERE/'cpu-gates.json',row)
        print(json.dumps(dict(passed=True,device_executed=False,proof_checks=runs[0]['checks'],full_checks=full_runs[0]['checks'],
                             proof_seconds=[r['elapsed_seconds'] for r in runs],full_seconds=[r['elapsed_seconds'] for r in full_runs])))

if __name__=='__main__':main()
