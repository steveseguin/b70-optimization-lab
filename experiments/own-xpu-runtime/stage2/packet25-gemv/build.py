#!/usr/bin/env python3
"""CPU-only build/gates. Never executes a SYCL executable, even --help."""
import hashlib,json,os,re,resource,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
B=HERE/'build'
IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
PRECISE=['-fno-fast-math','-ffp-contract=off']
DEVICE=['-fsycl','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def dependencies(start):
    todo=list(start);seen=set()
    while todo:
        p=todo.pop().resolve()
        if p in seen:continue
        seen.add(p)
        for name in re.findall(r'^\s*#\s*include\s*"([^"]+)"',p.read_text(),re.M):
            q=(p.parent/name).resolve()
            if not q.is_file():raise ValueError('unclosed header: '+str(q))
            todo.append(q)
    return seen

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    B.mkdir(exist_ok=True);scratch=B/'compile-scratch';scratch.mkdir(exist_ok=True)
    os.environ['TMPDIR']=str(scratch)
    receipt=dict(schema='packet25.build.v1',passed=False,device_executed=False,commands=[],max_compile_jobs=1,memory_limit_bytes=8*1024**3)
    def run(argv,tag,ok=True):
        argv=list(map(str,argv));r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True)
        (B/(tag+'.log')).write_text(r.stdout+r.stderr)
        receipt['commands'].append(dict(argv=argv,returncode=r.returncode,log='build/'+tag+'.log'))
        if ok and r.returncode:raise RuntimeError(tag+' failed: '+r.stderr[-3000:])
        return r
    try:
        artifacts={}
        for label,compiler,src,flags in [
          ('host-gcc','g++','host.cpp',['-DHOST_ONLY','-fno-tree-vectorize']),
          ('host-icpx',IC,'host.cpp',['-DHOST_ONLY','-fdenormal-fp-math=ieee','-fno-vectorize','-fno-slp-vectorize']),
          ('device-gemv',IC,'native.cpp',DEVICE)]:
            obj=scratch/(label+'.o');binary=B/label
            common=['-std=c++20','-O2',*PRECISE,*flags]
            compile=[compiler,*common,'-c',HERE/src,'-o',obj]
            link=[compiler,*common,obj,'-o',binary]
            for cmd in (compile,link):
                assert all(flag in cmd for flag in PRECISE)
                if label=='device-gemv':assert all(flag in cmd for flag in DEVICE)
            run(compile,label+'-compile');run(link,label+'-link')
            artifacts['build/'+label]=sha(binary)
        # ELF reads only; do not load or execute native executable.
        for label in ('host-gcc','host-icpx'):
            elf=run(['readelf','-d',B/label],label+'-dependencies').stdout
            assert not any(x in elf.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
        receipts=[]
        for label in ('host-gcc','host-icpx'):
            for repeat in (1,2):
                out=B/(label+'-repeat'+str(repeat)+'.json');run([B/label,out],out.stem)
                data=json.loads(out.read_text());assert data['passed'] and not data['device_executed'];receipts.append(data)
        assert all(r==receipts[0] for r in receipts),'cross-compiler/fresh-process bytes differ'
        cpu=dict(receipts[0],compilers=['g++',IC],fresh_processes=4,binary_hashes={k:v for k,v in artifacts.items() if 'host-' in k},arithmetic='iq3-p17-detmath-v2',real_model_qualified=False)
        save(HERE/'cpu-tests.json',cpu)
        tests=run([sys.executable,'-B',HERE/'test_window.py'],'window-tests')
        summary=run([sys.executable,'-B',HERE/'test_summary.py'],'summary-tests')
        sizes={}
        for line in run(['nm','-S','-C',B/'device-gemv'],'captures').stdout.splitlines():
            if 'p25::capture_size<' in line:
                parts=line.split(None,3);sizes[parts[3]]=int(parts[1],16)
        assert len(sizes)>=50 and max(sizes.values())<=1024
        save(HERE/'kernel-sizes.json',dict(passed=True,device_executed=False,measurement='compiler-emitted sizeof(F) symbol sizes; same static guard as packet23',sizes=sizes,max_capture_bytes=max(sizes.values())))
        probe=scratch/'oversized.cpp';probe.write_text('#include "'+str(HERE/'device.hpp')+'"\nvoid probe(){p25::checked(std::array<char,1025>{});}\n')
        reject=run([IC,'-std=c++20','-fsycl','-fsyntax-only',probe],'oversized-rejected',ok=False)
        assert reject.returncode and 'device kernel capture exceeds 1024 bytes' in reject.stderr
        kernel=(HERE/'device.hpp').read_text();assert kernel.count('h.parallel_for(')==kernel.count('checked([=]')==2
        # Platform transcendentals/reassociation are forbidden in new arithmetic.
        matches=[]
        for file in ('candidates.hpp','device.hpp','fixtures.hpp'):
            for n,line in enumerate((HERE/file).read_text().splitlines(),1):
                if re.search(r'(?:sycl|std)::(?:exp|log|sqrt|rsqrt|fma)\s*\(|(?:native|fast_math)::|#pragma\s+.*fast',line):matches.append([file,n,line])
        assert not matches
        save(HERE/'math-gate.json',dict(passed=True,device_executed=False,matches=matches,compile_and_link_precision_asserted=True,nonlinear_scope='no nonlinear arithmetic included in GEMV outputs'))
        deps=dependencies([HERE/'native.cpp',HERE/'host.cpp'])
        deps.update({HERE.parent/'packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan/run-r5e-class-times-cards01/class-times.json', ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'})
        receipt.update(passed=True,artifacts_sha256=artifacts,cpu_receipt_sha256=sha(HERE/'cpu-tests.json'),external_sources_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(deps) if HERE not in p.parents},sources_sha256={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and (p.suffix in ('.hpp','.cpp','.py','.txt') or p.name=='timing-plan.json')},peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    except Exception as e:
        receipt['error']=str(e);print(str(e),flush=True)
    finally:
        shutil.rmtree(scratch);receipt['compile_scratch_removed']=True
        save(HERE/'build-receipt.json',receipt)
    print('PASS' if receipt['passed'] else 'FAIL',flush=True)
    return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
