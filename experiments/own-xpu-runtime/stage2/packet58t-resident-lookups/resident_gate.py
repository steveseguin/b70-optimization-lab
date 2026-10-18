"""Bounded native copy/dequant/fault and complete miniature-engine equality gates."""
import argparse,json,os,resource,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,BASE,sha,save,limits,compiler_turn
ENV=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300,env=ENV)
    if r.returncode:raise RuntimeError(r.stdout[-1000:]+r.stderr[-3000:])
    return r

def copy_gate():
    records=[]
    with tempfile.TemporaryDirectory(prefix='resident-',dir=P/'build') as tmp:
        tmp=Path(tmp)
        for compiler,tag in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','intel')]:
            binary=tmp/tag
            cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-I'+str(BASE.parent/'packet2/kernels'),P/'native/resident_cpu.cpp','-lcrypto','-o',binary]
            with compiler_turn():r=run(cmd)
            (P/'evidence'/f'{tag}-resident-build.log').write_text(r.stdout+r.stderr)
            for repeat in range(2):
                path=tmp/f'{tag}-{repeat}.bin';row=json.loads(run([binary,path]).stdout);path.unlink()
                row.update(compiler=tag,repeat=repeat,binary_sha256=sha(binary),command=list(map(str,cmd)))
                records.append(row);print(tag,repeat,'copy/hash/dequant/fault PASS',flush=True)
    assert len({r['bf16_output_sha256'] for r in records})==1
    save(P/'evidence/resident-copy-cpu.json',dict(passed=True,device_executed=False,records=records,
        limitation='Bounded synthetic packed file; not a cold disk benchmark or full production allocation.',
        sources={str(f.relative_to(P.parents[3])):sha(f) for f in (P/'resident_gate.py',P/'native/resident_lookup.hpp',P/'native/resident_cpu.cpp',BASE.parent/'packet2/kernels/math.hpp')}))

def miniature():
    rows=[]
    with tempfile.TemporaryDirectory(prefix='engine-',dir=P/'build') as directory:
        tmp=Path(directory)
        def fixtures(out):return {str(f.relative_to(out)):sha(f) for f in sorted(out.glob('step*/*')) if f.is_file()}
        ref=None
        for mode in ('gnu-host','intel-host'):
            binary=P/'build'/mode/'own-rt-iq3'
            base=[binary,'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8','--retain-steps','1-8','--selection',P/'selection.json','--selection-sha256',sha(P/'selection.json')]
            for repeat in range(2):
                original=tmp/f'{mode}-{repeat}-original';candidate=tmp/f'{mode}-{repeat}-resident'
                run([*base,'--output',original]);run([*base,'--resident-lookups','--output',candidate])
                a=fixtures(original);b=fixtures(candidate);assert a and a==b
                x=json.loads((original/'result.json').read_text());y=json.loads((candidate/'result.json').read_text());assert x['tokens']==y['tokens']
                if ref is None:ref=a
                assert a==ref,'cross-compiler full engine differs'
                # Parent 58p uses these exact unchanged 58j model entry binaries.
                if repeat==0 and mode=='gnu-host':
                    parent=tmp/'frozen58p';run([P.parent/'packet58p-onecard-record/build/gnu-host/own-rt-iq3',*base[1:],'--output',parent]);assert fixtures(parent)==a
                r=json.loads((candidate/'receipt.json').read_text());assert r['lookup_residency']['enabled']
                assert all(t['source_sha256']==t['resident_sha256'] for t in r['lookup_residency']['tensors'])
                timing=[json.loads(line) for line in (candidate/'timings.jsonl').read_text().splitlines()]
                assert timing and all(x['resident_lookups'] and x['prepare_major_faults']==0 for x in timing)
                rows.append(dict(preparation_major_faults=0,preparation_steps=len(timing),compiler=mode,repeat=repeat,passed=True,compared_files=len(a),tokens=y['tokens'],binary_sha256=sha(binary),lookup_residency=r['lookup_residency']))
                shutil.rmtree(original);shutil.rmtree(candidate)
            print(mode,'complete outputs PASS',flush=True)
        # Same engine, actual resets, three backing switches, unchanged storage.
        binary=P/'build/gnu-host/own-rt-iq3';tokens=tmp/'tokens';tokens.write_text('2 5 3 7 1\n')
        oracle=tmp/'oracle';oracle.write_text(' '.join(map(str,rows[0]['tokens']))+'\n')
        suite=tmp/'suite';suite.write_text(f'a {tokens} {oracle}\n')
        from screen_views import write_table,selection
        base[base.index('--selection')+1]=selection('tile16')
        table=tmp/'bracket';write_table(table,'resident')
        out=tmp/'bracket-out';run([binary,*base[1:],'--suite-inputs',suite,'--bracket-inputs',table,'--output',out])
        arenas=set()
        for label in ('A0','B0','A1'):
            assert fixtures(out/label/'a')==ref
            b=json.loads((out/label/'lookup-backing.json').read_text());assert b['resident']==(label=='B0')
            arenas.add(json.loads((out/label/'boundary.json').read_text())['arena_descriptors_sha256'])
        assert len(arenas)==1
        # Fail closed on target token mismatch; no candidate may run.
        wrong=list(rows[0]['tokens']);wrong[0]=(wrong[0]+1)%32;oracle.write_text(' '.join(map(str,wrong))+'\n');bad=tmp/'bad'
        result=subprocess.run(list(map(str,[binary,*base[1:],'--suite-inputs',suite,'--bracket-inputs',table,'--output',bad])),stdin=subprocess.DEVNULL,capture_output=True,text=True,env=ENV)
        assert result.returncode and not (bad/'B0').exists()
    save(P/'evidence/resident-engine-cpu.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,
        reference_file_sha256=ref,frozen58p_output_equal=True,cross_compiler_equal=True,bracket_reset_equal=True,wrong_oracle_refused=True,
        full_production_packet49_device_parity='pending'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('gate',choices=('copy','engine'));a=ap.parse_args();limits()
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    {'copy':copy_gate,'engine':miniature}[a.gate]()
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<8*1024**3
if __name__=='__main__':main()
