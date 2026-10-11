#!/usr/bin/env python3
"""Run packet19's checker against packet18, retaining source and v2 bindings."""
import argparse, hashlib, json, os, shutil, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
BUILD=HERE/'build'; RUNROOT=None; INPUT=BUILD/'input'; BIN=BUILD/'sanitized/depcheck-runtime'
ORACLE=HERE.parents[3]/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(name,data):(HERE/name).write_text(json.dumps(data,indent=2)+'\n')
def run(name,seed,cards=2,mode='parallel',tokens=None,count=3):
    out=RUNROOT/name
    report=out.with_suffix('.san.json')
    args=[str(BIN),'--card','0','--cards',str(cards),'--memory','resident' if cards==2 else 'layer-streaming',
          '--nongemv',mode,'--max-new',str(count),'--output',str(out)]
    if tokens is None:args+=['--mini']
    else:
        available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
        assert available>70*1024**3, 'resident sanitizer needs >70 GiB'
        args+=['--stage','decode','--context','256','--input',str(tokens),'--plan',str(INPUT/'plan.tsv'),
               '--identity',str(INPUT/'identity.tsv'),'--model-dir',read(INPUT/'input.json')['model_dir']]
    env=dict(os.environ,DEPCHECK_SEED=str(seed),DEPCHECK_REPORT=str(report))
    start=time.monotonic()
    with out.with_suffix('.log').open('w') as f:
        result=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=10900)
    san=read(report);r=read(out/'receipt.json')
    fixtures={str(f.relative_to(out)):sha(f) for f in sorted(out.glob('step*/layer-*.bf16'))}
    data=dict(name=name,seed=seed,cards=cards,mode=mode,argv=args,returncode=result.returncode,
              seconds=time.monotonic()-start,sanitizer=san,tokens=r['tokens'],fixtures=fixtures,
              binary_sha256=sha(BIN),source_manifest_sha256=sha(BIN.parent/'build.json'),
              buffers_sha256=sha(out/'buffers.json') if (out/'buffers.json').exists() else None,
              timings=[json.loads(x) for x in (out/'timings.jsonl').read_text().splitlines()],
              passed=result.returncode==0 and r['passed'] and not san['violations'],
              device_executed=False)
    save('sanitizer-'+name+'.json',data)
    assert data['passed'], name
    print(name,'PASS',round(data['seconds'],1),'seconds; zero violations',flush=True)
    return data
def main():
    parser=argparse.ArgumentParser();parser.add_argument('gate',choices=['mini','integration','real','all']);parser.add_argument('--run-root',type=Path);parser.add_argument('--tag',choices=['sanitized','lifetime-sanitized'],default='sanitized');a=parser.parse_args()
    global RUNROOT, BIN
    BIN=BUILD/a.tag/'depcheck-runtime'
    RUNROOT=(a.run_root or BUILD/f'sanitizer-{time.time_ns()}').resolve()
    assert BUILD.resolve() in RUNROOT.parents and not RUNROOT.exists(), 'fresh sanitizer output beneath build required'
    RUNROOT.mkdir(parents=True)
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    dynamic=subprocess.check_output(['readelf','-d',str(BIN)],text=True)
    assert not any(x in dynamic.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
    seeds=(0,1,17,73);rows=[]
    if a.gate in ('mini','all'):
        for mode in ('core','parallel'):
            expected=None
            for cards in (1,2):
                for seed in seeds:
                    r=run(f'mini-{mode}-{cards}-{seed}',seed,cards,mode)
                    identity=(r['tokens'],r['fixtures'],r['buffers_sha256'])
                    if expected is None:expected=identity
                    assert identity==expected
                    rows.append(r)
        save('sanitizer-mini.json',dict(passed=True,runs=len(rows),seeds=seeds,cards=[1,2],modes=['core','parallel'],violations=0,device_executed=False))
    if a.gate in ('integration','all'):
        import test
        rows=[]
        for seed in seeds:
            for mode in ('core','parallel'):
                os.environ['DEPCHECK_SEED']=str(seed)
                os.environ['DEPCHECK_REPORT']=str(BUILD/'integration-sanitizer.json')
                result=test.run(BIN,RUNROOT/f'integration-{seed}-{mode}',INPUT,mode)
                rows.append(dict(seed=seed,mode=mode,result=result))
                print('integration',seed,mode,len(result['tests']),'PASS',flush=True)
        os.environ.pop('DEPCHECK_REPORT',None);os.environ.pop('DEPCHECK_SEED',None)
        save('sanitizer-integration.json',dict(passed=True,runs=rows,cases_per_mode=13,seeds=seeds,device_executed=False))
    if a.gate in ('real','all'):
        scratch=RUNROOT/'input';scratch.mkdir(exist_ok=True)
        tokens=scratch/'tokens.txt';tokens.write_text('\n'.join((INPUT/'tokens.txt').read_text().split()[:2])+'\n')
        shutil.copyfile(INPUT/'vocab.bin',scratch/'vocab.bin')
        rows=[run(f'real-short-{seed}',seed,tokens=tokens,count=2) for seed in seeds]
        assert all((r['tokens'],r['fixtures'])==(rows[0]['tokens'],rows[0]['fixtures']) for r in rows)
        save('sanitizer-real-short.json',dict(passed=True,seeds=seeds,positions=3,generated_tokens=2,fixtures=96,violations=0,
             tokens=rows[0]['tokens'],input_tokens=(INPUT/'tokens.txt').read_text().split()[:2],device_executed=False))
        r=run('real-full',17,tokens=INPUT/'tokens.txt',count=1)
        hashes={f'step1/layer-{i:02}.bf16':sha(ORACLE/f'step1/layer-{i:02}.bf16') for i in range(48)}
        assert r['fixtures']==hashes and r['tokens']==read(ORACLE/'result.json')['tokens'][:1]
        save('sanitizer-real-full.json',dict(passed=True,positions=87,layer_matches=48,tokens=r['tokens'],binary_sha256=r['binary_sha256'],source_manifest_sha256=r['source_manifest_sha256'],execution_sanitizer=r['sanitizer'],
             oracle_sha256=sha(ORACLE/'result.json'),oracle_layers=hashes,violations=0,device_executed=False))
if __name__=='__main__':main()
