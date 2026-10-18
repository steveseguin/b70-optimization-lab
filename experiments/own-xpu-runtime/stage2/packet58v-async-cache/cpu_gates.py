"""Full-size binding, reset and miniature byte gates. No device executable runs."""
import argparse,hashlib,json,os,resource,shutil,subprocess,tempfile,time
from pathlib import Path
from build_engine import sha,save,limits,compiler_turn
from native_source import BASE
from views import P,VIEWS,selection,digest,write_table

ENV=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2')

def run(cmd,**kwargs):
    result=subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,env=ENV,timeout=600,**kwargs)
    if result.returncode:raise RuntimeError(result.stdout[-1000:]+result.stderr[-3500:])
    return result

def fullshape():
    rows=[];binary=P/'build/gnu-host/fullshape-submit'
    with tempfile.TemporaryDirectory(prefix='shape-',dir=P/'build') as directory:
        tmp=Path(directory)
        for view in ('serial','overlap'):
            for miss in ('zero-copy',):
                out=tmp/(view+'-'+miss)
                result=run([binary,'--fullshape-submit-test',out,selection(view),'WSCREEN',miss])
                row=json.loads((out/'result.json').read_text())
                assert row['passed'] and row['contexts']==[32,4096]
                rows.append(dict(view=view,miss_path=miss,result=row,stdout=result.stdout))
                if view=='serial' and miss=='zero-copy':
                    save(P/'evidence/fullshape-census.json',json.loads((out/'census.json').read_text()))
                shutil.rmtree(out)
                print('fullshape',view,miss,'PASS',flush=True)
        out=tmp/'postload';run([binary,'--postload-allocation-test',out])
        # Keep exact original test receipt, not an invented fit measurement.
        candidates=list(out.glob('*.json'))
        assert candidates
        shutil.copyfile(out/'census.json',P/'evidence/postload-census.json')
        save(P/'evidence/postload-allocation-cpu.json',dict(passed=True,device_executed=False,binary_sha256=sha(binary),
            native={f.name:json.loads(f.read_text()) for f in candidates}))
    save(P/'evidence/fullshape-submit-cpu.json',dict(passed=True,device_executed=False,binary_sha256=sha(binary),
        checks=len(rows),switches_per_check=5,rows=rows,peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))

def miniature():
    binary=P/'build/gnu-host/own-rt-iq3';rows=[]
    with tempfile.TemporaryDirectory(prefix='reset-',dir=P/'build') as directory:
        tmp=Path(directory);tokens=tmp/'input.tokens';tokens.write_text('2 5 3 7 1\n')
        other=tmp/'other.tokens';other.write_text('7 2 8 3 2\n')
        base=[binary,'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8','--retain-steps','1-8']
        fresh=tmp/'fresh';run([*base,'--input',tokens,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',fresh])
        expected=json.loads((fresh/'result.json').read_text())['tokens']
        fixture=lambda out:{str(f.relative_to(out)):sha(f) for f in sorted(out.glob('step*/*')) if f.is_file()}
        reference=fixture(fresh);assert reference
        expected_file=tmp/'oracle.txt';expected_file.write_text(' '.join(map(str,expected))+'\n')
        other_out=tmp/'fresh-other';run([*base,'--input',other,'--output',other_out])
        other_expected=tmp/'other-oracle.txt';other_expected.write_text(' '.join(map(str,json.loads((other_out/'result.json').read_text())['tokens']))+'\n')
        suite=tmp/'suite.tsv';suite.write_text(f'other {other} {other_expected}\na {tokens} {expected_file}\n')
        for view in ('overlap',):
            table=tmp/'bracket.tsv';write_table(table,view)
            for repeat in range(2):
                out=tmp/f'{view}-{repeat}'
                run([*base,'--suite-inputs',suite,'--bracket-inputs',table,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',out])
                identities=set()
                for label in ('A0','B0','A1','B1','A2'):
                    assert fixture(out/label/'a')==reference
                    assert json.loads((out/label/'a/result.json').read_text())['tokens']==expected
                    boundary=json.loads((out/label/'boundary.json').read_text());identities.add(boundary['arena_descriptors_sha256'])
                assert len(identities)==1
                rows.append(dict(view=view,repeat=repeat,passed=True,all_layer_bytes_equal=True))
                shutil.rmtree(out)
            print('miniature',view,'PASS',flush=True)
        # Wrong oracle fails during A0; no B0 request is allowed to run.
        expected_file.write_text(str((expected[0]+1)%32)+'\n')
        out=tmp/'bad-oracle'
        result=subprocess.run(list(map(str,[*base,'--suite-inputs',suite,'--bracket-inputs',table,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',out])),stdin=subprocess.DEVNULL,capture_output=True,text=True,env=ENV,timeout=60)
        assert result.returncode!=0 and 'oracle token mismatch' in result.stderr and not (out/'B0').exists()
        proof=json.loads((out/'receipt.json').read_text());assert not proof['passed'] and proof['safe_to_exit']
    save(P/'evidence/reset-gate.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,
        binary_sha256=sha(binary),compared_files_per_request=len(reference),oracle_negative_passed=True))

def bytes_gate():
    records=[];transcripts={};sources={};started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='bytes-',dir=P/'build') as directory:
        tmp=Path(directory)
        for compiler in ('/usr/bin/g++','/opt/intel/oneapi/compiler/2026.0/bin/icpx'):
            tag='gnu' if compiler.endswith('g++') else 'intel'
            for stem,args in [('p100_cpu',['down-tile16']),('p82_cpu',['rec-both-plus']),('p58j_route_cpu',[])]:
                source=P/'native'/(stem+'.cpp');sources[str(source.relative_to(P.parents[3]))]=sha(source)
                binary=tmp/(tag+'-'+stem)
                cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-Wno-unknown-pragmas',
                    '-I'+str(BASE),'-I'+str(P/'../../stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(source),'-o',str(binary),'-lcrypto']
                with compiler_turn():
                    result=run(cmd)
                (P/'evidence'/f'{tag}-{stem}-build.log').write_text(result.stdout+result.stderr)
                for repeat in range(2):
                    out=tmp/f'{tag}-{stem}-{repeat}';out.mkdir()
                    result=run([binary,*args,out])
                    (P/'evidence'/f'{tag}-{stem}-{repeat}.log').write_text(result.stdout+result.stderr)
                    a=(out/'expected.bin').read_bytes();b=(out/'candidate.bin').read_bytes();assert a==b
                    transcripts[tag,stem,repeat]=a.splitlines()
                    records.append(dict(compiler=tag,fixture=stem,repeat=repeat,passed=True,transcript_sha256=sha(out/'expected.bin'),binary_sha256=sha(binary),command=cmd))
                    if repeat==0:
                        for leaf in ('expected.bin','native.json','cases.jsonl'):
                            if (out/leaf).exists():
                                target='transcript.txt' if leaf=='expected.bin' else leaf
                                shutil.copyfile(out/leaf,P/'evidence'/f'{tag}-{stem}-{target}')
                    shutil.rmtree(out)
                print('bytes',tag,stem,'PASS',flush=True)
        cross={}
        for stem in ('p100_cpu','p82_cpu','p58j_route_cpu'):
            for tag in ('gnu','intel'):assert transcripts[tag,stem,0]==transcripts[tag,stem,1]
            a=transcripts['gnu',stem,0];b=transcripts['intel',stem,0];assert len(a)==len(b)
            differences=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
            if differences:
                assert stem=='p82_cpu'
                cases=[json.loads(x)['case'] for x in (P/'evidence/gnu-p82_cpu-cases.jsonl').read_text().splitlines()]
                assert all('-s6-' in cases[i] for i in differences),'finite recurrence differs'
            cross[stem]=dict(equal=not differences,baseline_nan_payload_differences=differences)
    save(P/'evidence/byte-gates.json',dict(passed=True,device_executed=False,records=records,cross_compiler=cross,sources=sources,
        per_view={v:dict(down='p100_cpu',route='p58j_route_cpu',recurrence='p82_cpu',unchanged_other_arithmetic=True) for v in VIEWS},seconds=time.monotonic()-started))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('gate',choices=('bytes','fullshape','reset'));a=ap.parse_args();limits()
    # Sparse full-shape mocks reserve >100 GB VA, but touch <100 MB RSS.
    # Only CPU gates using actual small allocations install the 4 GiB AS cap.
    if a.gate!='fullshape':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    {'bytes':bytes_gate,'fullshape':fullshape,'reset':miniature}[a.gate]()
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<4*1024**3
    limits()

if __name__=='__main__':main()
