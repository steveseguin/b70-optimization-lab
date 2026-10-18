"""Fresh GNU/Intel linked split32 checks and inherited draft-HC determinism."""
import gzip,json,shutil,subprocess
from build_engine import P,ROOT,B,BASE,sha,save,limits
from compile_turn import turn
def main():
    limits();dest=B/'cpu';dest.mkdir(exist_ok=True)
    prior=json.loads((BASE/'engine-commands.json').read_text())
    original=next(r['command'] for r in prior if r['name']=='gnu-host-link')
    mirror=B/'checked'/P.relative_to(ROOT)
    sources={};runs=[];commands=[]
    def run(cmd,log):
        commands.append(list(map(str,cmd)))
        with turn(),log.open('w') as f:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
    flags=['-std=c++20','-O2','-fPIE','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY',
           '-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src')]
    for label,cxx in (('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')):
        objects=[]
        for stem in ('p49_qsa_fixture','p49_qsa_submit'):
            obj=dest/(stem+'-'+label+'.o');objects.append(obj)
            run([cxx,*flags,'-c',str(mirror/(stem+'.cpp')),'-o',str(obj)],P/'evidence'/(stem+'-'+label+'-compile.log'))
        link=[x for x in original if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o') and not x.endswith('p49_qsa_submit.cpp.o')]
        link[0]=cxx
        if label=='Intel':link=[('-lgomp' if x=='-fopenmp' else x) for x in link]
        for f in link:
            if f.endswith('.o'):sources[str(__import__('pathlib').Path(f).relative_to(ROOT))]=sha(f)
        binary=dest/('qsa-'+label);link[link.index('-o')+1]=str(binary)
        link[link.index('-o'):link.index('-o')]=list(map(str,objects))
        run(link,P/'evidence'/('qsa-'+label+'-link.log'))
        hc=dest/('hc-'+label)
        run([cxx,*flags,str(P/'p59_fixture.cpp'),'-o',str(hc)],P/'evidence'/('hc-'+label+'-compile.log'))
        for repeat in (1,2):
            for kind in ('qsa','hc'):
                scratch=dest/'scratch';scratch.mkdir()
                try:
                    cmd=[str(binary),'--output',str(scratch)] if kind=='qsa' else [str(hc),str(scratch/'output.bin')]
                    result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)
                    raw=scratch/'output.bin';digest=sha(raw);out=P/'evidence'/(kind+'-'+label+'-'+str(repeat)+'.bin.gz')
                    out.write_bytes(gzip.compress(raw.read_bytes(),mtime=0))
                    native=json.loads((scratch/'receipt.json').read_text()) if kind=='qsa' else {'passed':True,'device_executed':False}
                    assert native['passed'] and not native['device_executed']
                    if kind=='qsa':assert native['checks']==88 and native['reference_exact']
                    for leaf in ('receipt.json','cases.jsonl'):
                        if (scratch/leaf).exists():shutil.copyfile(scratch/leaf,P/'evidence'/(kind+'-'+label+'-'+str(repeat)+'-'+leaf))
                    sources[str(out.relative_to(ROOT))]=sha(out)
                    runs.append(dict(kind=kind,compiler=label,repeat=repeat,command=cmd,
                         fixture=str(out.relative_to(ROOT)),fixture_sha256=sha(out),raw_sha256=digest,
                         bytes=raw.stat().st_size,native=native))
                    print(kind,label,repeat,'PASS',flush=True)
                finally:shutil.rmtree(scratch)
        for f in [*objects,binary,hc]:f.unlink()
    for kind in ('qsa','hc'):
        assert len({r['raw_sha256'] for r in runs if r['kind']==kind})==1,(kind,'determinism/compiler mismatch')
    from math_gate import closure
    for f in [*closure(),P/'p59_fixture.cpp',P/'cpu_gate.py',P/'compile_turn.py',P/'build_engine.py']:
        sources[str(f.relative_to(ROOT))]=sha(f)
    save(P/'evidence/cpu-gates.json',dict(passed=True,device_executed=False,cpu_model_executed=False,
         scope='Split32 equals its fixed arithmetic reference in 88 linked cases per run; two fresh processes per compiler. HC unchanged and deterministic. No old-draft arithmetic parity asserted.',
         runs=runs,sources=sources,commands=commands))
if __name__=='__main__':main()
