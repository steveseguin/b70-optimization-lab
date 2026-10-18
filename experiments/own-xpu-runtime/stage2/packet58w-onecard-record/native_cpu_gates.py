"""CPU-only parser, full production shape, postload and mixed-source byte gates."""
import hashlib,json,os,resource,shutil,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
    assert r.returncode==0,(list(map(str,cmd)),r.stderr[-4000:]);return r

def main():
    import suite_driver as D
    import views as V
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000
    parent=json.loads((P/'lineage/58v-build-receipt.json').read_text())
    for leaf,digest in parent['artifacts'].items():assert sha(P/leaf)==digest
    full=P/'build/gnu-host/fullshape-submit';binary=P/'build/gnu-host/own-rt-iq3'
    rows=[];parsers=[]
    with tempfile.TemporaryDirectory(prefix='cpu-',dir=P/'build') as directory:
        tmp=Path(directory)
        manifest=D.oracle_inputs()
        for window in D.WINDOWS:
            out=tmp/window
            run([full,'--fullshape-submit-test',out,V.selection('down-tile16'),window,'zero-copy'])
            row=json.loads((out/'result.json').read_text())
            assert row['passed'] and row['contexts']==[32,4096]
            rows.append(dict(window=window,miss_path='zero-copy',result=row))
            if window=='KD':shutil.copyfile(out/'census.json',P/'evidence/fullshape-census.json')
            shutil.rmtree(out)
            table=tmp/(window+'.tsv')
            entries=manifest['prompts'][:1] if window in ('KD','W2m') else manifest['prompts']
            table.write_text(''.join(f"{e['prompt_id']} {ROOT/e['input_bundle']/'tokens.txt'}\n" for e in entries))
            cap=8 if window in ('KD','W2m') else 128
            retain='1-8' if window in ('KD','W2m','WS') else 'none'
            historical=P.parent/'packet58p-onecard-record/evidence/card0-58p-a'/window/'run/run'
            compared=[D.compare_request(historical/e['prompt_id'],D.ORACLE/'results'/e['prompt_id'],e,cap,retain) for e in entries]
            assert all(r['exact_oracle'] for r in compared)
            native=D.native_command(SimpleNamespace(window=window,view='down-tile16',miss_mode='zerocopy',output=out),manifest,table)
            cmd=[binary,'--p58r-parse-test',*native[3:]];cmd.remove('--authorized-device-window');cmd[cmd.index('--native-nice')+1]='19'
            run(cmd)
            parsed=json.loads((out/'run/parser.json').read_text());assert parsed['passed'] and not parsed['device_executed']
            bad=[str(x) for x in cmd];bad[bad.index('--cache-maintenance')+1]='bogus'
            negative=subprocess.run(bad,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert negative.returncode!=0 and 'cache maintenance mode' in negative.stderr
            parsers.append(dict(window=window,miss_path='zero-copy',native_argv=native,cpu_parser_argv=list(map(str,cmd)),passed=True,negative_refused=True,negative_error=negative.stderr.strip(),host_oracle_replay=dict(requests=len(compared),compared_layer_fixtures=sum(r['compared_layer_fixtures'] for r in compared),source=str(historical.relative_to(ROOT)),new_device_claim=False)))
            shutil.rmtree(out)
            print(window,'full shape and native parser PASS',flush=True)
        out=tmp/'postload';run([full,'--postload-allocation-test',out])
        native={f.name:json.loads(f.read_text()) for f in out.glob('*.json')}
        assert native['result.json']['passed']
        shutil.copyfile(out/'census.json',P/'evidence/postload-census.json')
        save(P/'evidence/postload-allocation-cpu.json',dict(passed=True,device_executed=False,native=native,binary_sha256=sha(full)))
        out=tmp/'k1';k1=P/'build/gnu-host/p58-cache-fixtures'
        run([k1,'--down-layout','down-tile16','--iterations','2','--output',out])
        k=json.loads((out/'k1.json').read_text())
        assert k['passed'] and not k['device_executed'] and all(k[x] for x in ('zero_copy_bytes_equal','mixed_bytes_equal','streamed_bytes_equal'))
        shutil.copyfile(out/'k1-cases.jsonl',P/'evidence/k1-cases.jsonl')
        k.update(binary_sha256=sha(k1),sources={str(Path(__file__).relative_to(ROOT)):sha(__file__)})
        save(P/'k1-cpu.json',k)
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/fullshape-submit-cpu.json',dict(passed=True,device_executed=False,binary_sha256=sha(full),checks=len(rows),records=rows,peak_child_rss_bytes=rss,sparse_virtual_arena=True))
    save(P/'evidence/startup-cpu.json',dict(passed=True,device_executed=False,binary_sha256=sha(binary),checks=len(parsers),records=parsers,fullshape_receipt_sha256=sha(P/'evidence/fullshape-submit-cpu.json'),peak_child_rss_bytes=rss))
    print('K1 mixed-source and postload PASS; peak child RSS',rss,flush=True)
if __name__=='__main__':
    # Full-shape mocks reserve >100 GB of sparse VA, touching bounded backing.
    # A physical RSS assertion enforces the 4 GiB ceiling; no AS cap here.
    main()
