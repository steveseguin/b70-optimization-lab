"""GNU/Intel real-row lookup bytes and complete miniature engine/reset parity."""
import json,os,resource,subprocess,tempfile
from pathlib import Path
from prepare import P,sha,save
from build_engine import run,compiler_turn,limits

def main():
    limits();records=[];math=next((P/'vendor').rglob('packet2/kernels/math.hpp'))
    env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2',**json.loads((P/'proposals/smoke.json').read_text())['environment']}
    with tempfile.TemporaryDirectory(prefix='p58an-resident-') as tmp:
        tmp=Path(tmp)
        for tag,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
            binary=P/'build'/f'{tag}-resident-bytes'
            run([cxx,'-std=c++20','-DOWN_RT_HOST_ONLY','-O2','-fno-fast-math','-ffp-contract=off','-I'+str(math.parent),str(P/'native/resident_cpu.cpp'),'-lcrypto','-o',str(binary)],tag+'-resident-bytes')
            for repeat in range(2):
                fixture=tmp/f'{tag}-{repeat}'
                with compiler_turn():cp=subprocess.run([str(binary),str(fixture)],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
                row=json.loads(cp.stdout);fixture.unlink();assert row['passed']
                records.append(dict(compiler=tag,repeat=repeat,binary_sha256=sha(binary),result=row));print(tag,repeat,'resident byte/dequant PASS',flush=True)
        assert len({r['result']['bf16_output_sha256'] for r in records})==1
        binary=P/'build/gnu-host/own-rt-iq3'
        base=[str(binary),'--mini','--pipeline-mini','--memory','resident','--cache-maintenance','overlap','--context','32','--tokens','8','--retain-steps','1-8','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--native-nice','19','--selection',str(P/'inputs/selection.json'),'--selection-sha256',sha(P/'inputs/selection.json')]
        def execute(cmd):
            with compiler_turn():cp=subprocess.run(cmd,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
            if cp.returncode:raise RuntimeError(cp.stdout[-2000:]+cp.stderr[-2000:])
        ref=None;engine=[]
        for repeat in range(2):
            for mode in ('mapped','resident'):
                out=tmp/f'engine-{repeat}-{mode}';execute(base+['--lookups',mode,'--output',str(out)])
                outputs={str(f.relative_to(out)):sha(f) for f in out.glob('step*/*') if f.is_file()}
                tokens=json.loads((out/'result.json').read_text())['tokens']
                assert outputs
                identity=dict(outputs=outputs,tokens=tokens)
                if ref is None:ref=identity
                assert identity==ref
                if mode=='resident':
                    receipt=json.loads((out/'receipt.json').read_text());assert receipt['lookup_residency']['enabled']
                    assert all(r['source_sha256']==r['resident_sha256'] for r in receipt['lookup_residency']['tensors'])
                engine.append(dict(repeat=repeat,mode=mode,files=len(outputs),tokens=tokens,passed=True))
        # The miniature mock has no demand transport backend. Exercise lookup
        # lifetime/reset here; real-shape demand views use preparation_gate.py
        # plus the separate GNU/Intel arithmetic and ownership byte fixtures.
        tokens=tmp/'tokens';tokens.write_text('2 5 3 7 1\n')
        suite=tmp/'suite';suite.write_text(f'a {tokens}\nb {tokens}\n')
        out=tmp/'reset-suite'
        execute(base+['--lookups','resident','--suite-inputs',str(suite),'--output',str(out)])
        for label in ('a','b'):
            folder=out/label;assert json.loads((folder/'result.json').read_text())['tokens']==ref['tokens']
            assert {str(f.relative_to(folder)):sha(f) for f in folder.glob('step*/*') if f.is_file()}==ref['outputs']
        engine.append(dict(kind='resident-two-request-reset',passed=True,reset_exact=True,
            demand_bracket_scope='real-argv preparation and real-shape byte gates, not miniature backend'))
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/resident-cpu.json',dict(passed=True,device_executed=False,records=records,engine=engine,
        max_rss_bytes=rss,limitations='synthetic real row shapes and miniature model; no full GGUF/device reads',
        sources={str(f.relative_to(P)):sha(f) for f in (P/'native/resident_lookup.hpp',P/'native/resident_weights.hpp',P/'native/resident_cpu.cpp',math)},engine_binary_sha256=sha(binary)))
if __name__=='__main__':main()
