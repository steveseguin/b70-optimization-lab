#!/usr/bin/env python3
"""Serial CPU capacity fixtures, exact cross-compiler receipts, no accelerator entry."""
import argparse, fcntl, gzip, hashlib, json, os, re, shlex, signal, subprocess, sys, time
from pathlib import Path
import storage
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
PREFIX=['nice','-n','19','ionice','-c','3']
REPORT=P/'capacity-fixture-gates.json'
LENGTHS={256:[88,104,120,136,152,256],4096:[88,152,1024,2048,2049,4096],32768:[88,152,1024,2048,4096,8192,32767]}

def require(ok,message):
    if not ok:raise RuntimeError(message)

def save(path,row):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(row,indent=2)+'\n');tmp.replace(path)

def digest(path):return storage.digest(path)

def source_identity(compiler,target):
    """Hash linked compilation inputs/header closure, not changing gate receipts."""
    table=json.loads((B/compiler/'compile_commands.json').read_text());selected=[]
    object_groups=('programs','fixture_validation',target) if target!='p33-linked-fixtures' else ('programs',target)
    for row in table:
        argv=row.get('arguments') or shlex.split(row['command'])
        if any('CMakeFiles/'+group+'.dir/' in ' '.join(argv) for group in object_groups):selected.append((row,argv))
    require(selected,'no matching compilation identity for '+target)
    files=set();commands=[]
    for row,argv in selected:
        source=Path(row['file']).resolve();roots=[P]
        for index,arg in enumerate(argv):
            if arg=='-I':roots.append(Path(argv[index+1]).resolve())
            elif arg.startswith('-I'):roots.append(Path(arg[2:]).resolve())
        def visit(path):
            path=path.resolve()
            if path in files:return
            require(path.is_relative_to(ROOT),'compiled source outside lab: '+str(path));files.add(path)
            for include in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"',path.read_text(errors='replace'),re.M):
                found=next((candidate for base in (path.parent,*roots) if (candidate:=base/include).is_file()),None)
                if found is not None:visit(found)
        visit(source);commands.append(argv)
    identities={str(f.relative_to(ROOT)):digest(f) for f in sorted(files)}
    return dict(compiled_sources_and_headers_sha256=identities,compile_commands=commands,
                driver_sha256=digest(Path(__file__)),storage_sha256=digest(P/'storage.py'))

def admit(reserve=100_000_000):
    r=storage.admit(reserve)
    require(r['build_bytes']+reserve<4_000_000_000,'CPU fixture build ceiling4GB exceeded; stop before writes')
    return r

def host(binary):
    r=subprocess.run(PREFIX+['readelf','-d',str(binary)],text=True,capture_output=True,check=True)
    require(not any(x in r.stdout.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl')),'accelerator-linked fixture binary refused')

def rss(pid):
    try:lines=Path(f'/proc/{pid}/status').read_text().splitlines()
    except FileNotFoundError:return 0
    return next((int(line.split()[1])*1024 for line in lines if line.startswith('RssAnon:')),0)

def execute(argv,log,seconds):
    peak=0;started=time.monotonic();failure=None
    with log.open('w') as output:
        process=subprocess.Popen(PREFIX+list(map(str,argv)),stdout=output,stderr=subprocess.STDOUT,
                                 env={**os.environ,'OMP_NUM_THREADS':'2'},cwd=P)
        try:
            while process.poll() is None:
                peak=max(peak,rss(os.getpid())+rss(process.pid))
                if peak>=8_000_000_000:raise RuntimeError('CPU fixture anonymous memory exceeded8GB')
                if time.monotonic()-started>seconds:raise RuntimeError('CPU fixture watchdog exceeded')
                time.sleep(.1)
        except BaseException as error:
            failure=error;process.send_signal(signal.SIGTERM)
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        code=process.wait()
    if failure:raise failure
    require(code==0,'CPU fixture failed: '+str(log))
    return dict(seconds=time.monotonic()-started,peak_aggregate_rss_anon_bytes=peak)

def pack(path,destination):
    """Hash then immediately compress, verifying exact decompressed bytes."""
    original=digest(path);count=path.stat().st_size;admit(count+1_000_000)
    destination.parent.mkdir(parents=True,exist_ok=True);temporary=destination.with_suffix(destination.suffix+'.tmp')
    with path.open('rb') as src,temporary.open('wb') as dst:
        with gzip.GzipFile(fileobj=dst,mode='wb',mtime=0) as archive:
            for block in iter(lambda:src.read(1024*1024),b''):archive.write(block)
    check=hashlib.sha256();total=0
    with gzip.open(temporary,'rb') as src:
        for block in iter(lambda:src.read(1024*1024),b''):check.update(block);total+=len(block)
    require(check.hexdigest()==original and total==count,'compressed fixture roundtrip')
    temporary.replace(destination)
    return dict(path=str(destination.relative_to(P)),sha256=digest(destination),raw_sha256=original,raw_bytes=count)

def shape_coverage(out,context):
    events=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
    wanted={f'qsa-c{context}-n{n}'+suffix for n in LENGTHS[context] for suffix in ('','-prepare','-pool','-select')}
    seen={r['workload'] for r in events if r.get('workload','').startswith('qsa-c')}
    require(seen==wanted,'K2 validation missing capacity/length/class binding')
    for name in wanted:
        rows=[r for r in events if r.get('workload')==name]
        require({r['variant'] for r in rows}=={'packet18','specialised'},'K2 missing reference/candidate binding')
        require(all(r['start_ns']==r['end_ns']==0 for r in rows),'host K2 timing must remainzero')
    return dict(lengths=LENGTHS[context],capacity_class_workloads=len(wanted),validation_only=True,
                arithmetic_evidence='nongemv arithmetic arms at identical registered lengths; this K2 arm checks bindings only')

def run_arm(compiler,kind,context,report,seconds):
    target='p33-linked-fixtures' if kind=='linked' else 'k2-fixtures' if kind=='k2-validation' else 'nongemv-fixtures'
    binary=B/compiler/target;host(binary);identity=source_identity(compiler,target)
    fixtures={str(f.relative_to(B/'fusion-fixtures')):digest(f) for f in sorted((B/'fusion-fixtures').glob('*')) if f.is_file()} if kind!='linked' else {}
    bound=dict(compiler=compiler,kind=kind,context=context,binary_sha256=digest(binary),sources=identity,fixtures_sha256=fixtures,
               dispatch_sha256=digest(P/'dispatch-p38.json'),rope_sha256=digest(P/'rope.bf16'))
    key=hashlib.sha256(json.dumps(bound,sort_keys=True).encode()).hexdigest()
    previous=next((r for r in report['rows'] if r.get('identity_key')==key and r.get('passed')),None)
    if previous:
        retained_root=Path(previous['scratch_retained']) if previous.get('scratch_retained') else None
        if retained_root is not None and retained_root.exists():
            if not previous.get('output_archive'):
                raw=retained_root/'run/output.bin';previous['output_archive']=pack(raw,P/'evidence'/'capacity-fixtures'/f'{key}-output.bin.gz');raw.unlink()
            if not previous.get('scratch_archive'):previous['scratch_archive']=storage.discard(retained_root)
            save(REPORT,report)
        for retained in ('output_archive','scratch_archive'):
            item=previous.get(retained);require(item and digest(P/item['path'])==item['sha256'],'cached fixture evidence missing')
        print('REUSE',compiler,kind,context,flush=True);return previous
    admission=admit();root=B/f'capacity-fixture-{compiler}-{kind}-{context}-{time.time_ns()}';root.mkdir();out=root/'run'
    row=dict(compiler=compiler,kind=kind,context=context,identity_key=key,binary_sha256=bound['binary_sha256'],
             passed=False,device_executed=False,identity=bound,storage_admission=admission)
    receipt=P/'evidence'/'capacity-fixtures'/f'{key}.json'
    argv=[binary,'--output',out]
    if kind=='linked':argv+=['--seconds','1800']
    else:argv+=['--context',str(context),'--fixtures',B/'fusion-fixtures','--dispatch',P/'dispatch-p38.json']
    if kind in ('k2-validation','nongemv-validation'):argv+=['--validate-only']
    row['command']=list(map(str,PREFIX+argv))
    try:
        row.update(execute(argv,root/'stdout.log',seconds));actual=json.loads((out/'receipt.json').read_text())
        require(actual['passed'] and not actual['device_executed'],'actual CPU fixture receipt failed')
        validation=kind.endswith('-validation');require(bool(actual.get('validation_only',False))==validation,'fixture validation mode mismatch')
        require(bool(actual['reference_exact'])==(not validation),'reference_exact scope differs')
        if kind=='linked':require(actual['checks']==216 and actual['split_instantiations']==36,'p33 instantiation coverage');checks=216
        else:
            require(actual['context']==context,'fixture context ignored')
            require(actual['source_fixtures']==(72 if kind=='k2-validation' else 93)+4*len(LENGTHS[context]),'capacity fixture coverage')
            expected=18+14*len(LENGTHS[context]) if kind=='k2-validation' else 116+9*len(LENGTHS[context])
            require(actual['fixtures']==expected,'nongemv fixture check count changed')
            checks=actual['fixtures']+actual['adapter_checks']
            if not validation:require(actual['packet18_exact'],'packet18 arithmetic mismatch')
        output_hash=digest(out/'output.bin');require(output_hash==actual['output_sha256'],'fixture output receipt hash mismatch')
        teardowns=actual.get('teardown',[]);teardowns=[teardowns] if isinstance(teardowns,dict) else teardowns
        require(teardowns and all(t.get('safe_to_exit') and t.get('exit_code')==0 and t.get('in_flight')==0 and t.get('live_bytes')==0 for t in teardowns),'fixture lifetime/teardown failed')
        row.update(output_sha256=output_hash,checks=checks,fixture_checks=actual.get('fixtures',actual.get('checks')),
                   receipt_sha256=digest(out/'receipt.json'),receipt={k:v for k,v in actual.items() if k!='teardown'},
                   teardown_summary=[{k:v for k,v in state.items() if k!='sequence'}|{'sequence_entries':len(state.get('sequence',[]))} for state in teardowns],
                   arithmetic=not validation,registered_lengths=[] if kind=='linked' else LENGTHS[context])
        if kind=='k2-validation':row['k2_capacity_binding_coverage']=shape_coverage(out,context)
        row['passed']=True;save(receipt,row)
        # Compress the output immediately after hashing. Its semantic comparison
        # receipt is already durable before any raw output is removed.
        try:
            row['output_archive']=pack(out/'output.bin',P/'evidence'/'capacity-fixtures'/f'{key}-output.bin.gz')
            (out/'output.bin').unlink()
        except Exception as error:row['compression_error']=str(error)
        save(receipt,row)
        if 'output_archive' in row:
            try:row['scratch_archive']=storage.discard(root)
            except Exception as error:row['retention_error']=str(error);row['scratch_retained']=str(root)
        else:row['scratch_retained']=str(root)
        save(receipt,row)
    except BaseException as error:
        row.update(passed=False,error=str(error));save(receipt,row)
        if root.exists():
            try:row['scratch_archive']=storage.discard(root)
            except Exception as retention:row['retention_error']=str(retention);row['scratch_retained']=str(root)
        report['rows'].append(row);save(REPORT,report);raise
    report['rows'].append(row);save(REPORT,report)
    print('PASS',compiler,kind,context,checks,'checks',flush=True);return row

def light_tests(report,seconds):
    modules=['test_k2_selection','test_k2_admission']
    sources={name:digest(P/(name+'.py')) for name in modules}
    for name in ('k2_summary.py','merge_dispatch.py','window.py','storage.py','test_storage_race.py','test_window_storage.py','dispatch-p38.json','kernel-registry.json','k2-class-registry.json'):sources[name]=digest(P/name)
    admit(5_000_000);root=B/f'capacity-fixture-light-{time.time_ns()}';root.mkdir()
    argv=[sys.executable,'-B','-m','unittest',*modules];row=dict(command=list(map(str,PREFIX+argv)),source_sha256=sources,device_executed=False)
    try:
        row.update(execute(argv,root/'tests.log',seconds));text=(root/'tests.log').read_text()
        found=re.search(r'Ran (\d+) tests?',text);require(found and re.search(r'\nOK(?:\s|$)',text),'light regression unittest summary')
        row.update(tests=int(found.group(1)))
        row['storage_race_execution']=execute([sys.executable,'-B',P/'test_storage_race.py'],root/'storage-race.log',seconds)
        race=json.loads((P/'storage-race-gates.json').read_text());require(race['passed'] and not race['device_executed'],'storage race regression failed')
        row['storage_race_checks']=len(race['checks'])
        row['window_storage_execution']=execute([sys.executable,'-B',P/'test_window_storage.py','--output',root/'window-storage.json'],root/'window-storage.log',seconds)
        window=json.loads((root/'window-storage.json').read_text());require(window['passed'] and not window['device_executed'],'window storage regression failed')
        row['window_storage_checks']=window['gates']
        row['passed']=True;save(P/'capacity-fixture-light-tests.json',row)
        row['archive']=storage.discard(root);save(P/'capacity-fixture-light-tests.json',row)
    except BaseException as error:
        row.update(passed=False,error=str(error));save(P/'capacity-fixture-light-tests.json',row)
        if root.exists():row['archive']=storage.discard(root)
        save(P/'evidence'/('light-failed-'+root.name+'.json'),row);save(P/'capacity-fixture-light-tests.json',row);raise
    report['light_tests']=row;save(REPORT,report)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('all','arithmetic','validation','light'),default='all')
    parser.add_argument('--compiler',choices=('both','gnu-host','icpx-host'),default='both')
    parser.add_argument('--context',type=int,choices=(256,4096,32768));parser.add_argument('--seconds',type=int,default=1800)
    parser.add_argument('--list',action='store_true');args=parser.parse_args()
    compilers=('gnu-host','icpx-host') if args.compiler=='both' else (args.compiler,)
    contexts=(args.context,) if args.context else (256,4096,32768)
    arms=[]
    if args.phase in ('all','arithmetic'):
        arms=[(compiler,'nongemv',context) for compiler in compilers for context in contexts]
        arms += [(compiler,'linked',None) for compiler in compilers]
    if args.phase in ('all','validation') and 'gnu-host' in compilers:
        arms += [('gnu-host','k2-validation',context) for context in contexts]
        arms += [('gnu-host','nongemv-validation',256)]
    if args.list:
        print(json.dumps(dict(arms=arms,light_tests=args.phase in ('all','light'),device_executed=False,planning_estimate='15–30 minutes total; unmeasured packet44 CPU estimate, per-arm watchdog1800s'),indent=2));return
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2','nice19 OMP2 required')
    B.mkdir(exist_ok=True);lock=(B/'capacity-fixture.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    report=json.loads(REPORT.read_text()) if REPORT.exists() else dict(schema='packet44.capacity-fixtures.v1',passed=False,device_executed=False,rows=[])
    report['passed']=False;selected=[run_arm(*arm,report,args.seconds) for arm in arms]
    if args.phase in ('all','light'):light_tests(report,args.seconds)
    hashes={};linked=None
    for context in contexts:
        rows=[r for r in selected if r['kind']=='nongemv' and r['context']==context]
        if len(rows)==2:
            require(rows[0]['output_sha256']==rows[1]['output_sha256'],'cross-compiler capacity fixture output differs')
            hashes[str(context)]=rows[0]['output_sha256']
    rows=[r for r in selected if r['kind']=='linked']
    if len(rows)==2:require(rows[0]['output_sha256']==rows[1]['output_sha256'],'cross-compiler p33 output differs');linked=rows[0]['output_sha256']
    if rows:
        save(P/'p33-linked-fixture-gates.json',dict(schema='packet44.p33-linked-fixtures.v1',passed=len(rows)==2 and all(r['passed'] for r in rows),device_executed=False,rows=rows,output_sha256=linked,p33_linked_fixture_host_sha256=linked,checks=sum(r['checks'] for r in rows)))
    report.update(passed=args.phase=='all' and args.compiler=='both' and args.context is None and len(selected)==12,
                  latest_invocation_passed=True,nongemv_fixture_host_sha256_by_context=hashes,p33_linked_fixture_host_sha256=linked,
                  arithmetic_checks=sum(r['checks'] for r in selected if r['arithmetic']),validation_checks=sum(r['checks'] for r in selected if not r['arithmetic']),no_speed_claim=True)
    save(REPORT,report);print(json.dumps({k:report[k] for k in ('passed','latest_invocation_passed','arithmetic_checks','validation_checks','nongemv_fixture_host_sha256_by_context','p33_linked_fixture_host_sha256')}))
if __name__=='__main__':main()
