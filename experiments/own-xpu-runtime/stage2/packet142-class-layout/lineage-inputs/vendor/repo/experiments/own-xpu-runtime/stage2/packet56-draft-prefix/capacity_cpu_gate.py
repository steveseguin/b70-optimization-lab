#!/usr/bin/env python3
"""Serial, resumable CPU model/rollback gates. Never executes a device binary."""
import argparse, fcntl, hashlib, json, os, subprocess, time
from pathlib import Path
import pipeline as pp
import storage
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
B=P/'build'
MANIFEST=P.parent/'suite-inputs-20261012/suite-manifest.json'
LEDGER=P/'capacity-cpu-gates.json'
PREFIX=['nice','-n','19','ionice','-c','3']

def save(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)

def source_identity():
    files=[f for f in P.rglob('*') if f.is_file() and B not in f.parents and
           (f.suffix in ('.cpp','.hpp') or f.name in ('pipeline.py','suite.py','storage.py','memory_gate.py','capacity_cpu_gate.py','dispatch-p38.json','dispatch-all-new.json','CMakeLists.txt','rope.bf16','mtp-manifest.tsv'))]
    return {str(f.relative_to(P)):storage.digest(f) for f in sorted(files)}

def host_binary(binary):
    text=subprocess.check_output(PREFIX+['readelf','-d',str(binary)],text=True).lower()
    pp.require(not any(x in text for x in ('libsycl','libze_loader','libur_loader','libopencl')),'CPU gate refuses accelerator-linked binary')

def admit(capacity,mini=False):
    # Final snapshots include full target/draft caches. This gate obeys the
    # operator's stricter 4 GB build ceiling; device wrappers have a 6 GB cap.
    reserve=20_000_000 if mini else 550_000_000+26*2368*max(0,capacity-256)
    admission=storage.admit(reserve)
    pp.require(admission['build_bytes']+reserve<4_000_000_000,
               'CPU scratch admission exceeds 4 GB build ceiling; stop and clear completed scratch before retry')
    return admission

class MemoryWatch:
    def __init__(self):self.pids={os.getpid()};self.peak=0;self.last=0.
    def launch(self,pid):self.pids.add(pid)
    def check(self):
        if time.monotonic()-self.last<.1:return
        self.last=time.monotonic();total=0
        for pid in tuple(self.pids):
            try:lines=Path(f'/proc/{pid}/status').read_text().splitlines()
            except FileNotFoundError:continue
            for line in lines:
                if line.startswith('RssAnon:'):total+=int(line.split()[1])*1024;break
        self.peak=max(self.peak,total)
        pp.require(total<8_000_000_000,'CPU coordinator plus rank RssAnon exceeded 8 GB')

def fixtures(out,layers):
    expected={f'step{step}/layer-{layer:02}.bf16' for step in range(1,9) for layer in range(layers)}
    result={}
    for rank in (0,1):
        base=out/f'rank{rank}'
        for f in base.glob('step*/layer-*.bf16'):
            name=str(f.relative_to(base));pp.require(name not in result,'duplicate rank fixture '+name)
            result[name]=storage.digest(f)
    pp.require(set(result)==expected,'missing or unexpected retained fixture files')
    return result

def entries(manifest):
    pp.require(manifest['arithmetic']=='iq3-p17-detmath-v2' and manifest['complete'],'suite manifest identity')
    chosen=sorted(manifest['prompts'],key=lambda r:(r['prompt_tokens'],r['prompt_id']))[:3]
    development=next(r for r in manifest['prompts'] if r['prompt_id']=='incident-retrospective')
    return chosen,development

def expected(entry):
    inp=ROOT/entry['input_bundle'];oracle=ROOT/entry['oracle_directory']
    for name,digest in entry['input_bundle_hashes'].items():
        pp.require(storage.digest(inp/name)==digest,'input bundle changed '+name)
    tokens=json.loads((oracle/'result.json').read_text())['tokens'][:8]
    pp.require(tokens==entry['first_8_token_ids'] and len(tokens)==8,'suite oracle prefix mismatch')
    hashes={f'step{s}/layer-{l:02}.bf16':storage.digest(oracle/f'step{s}/layer-{l:02}.bf16') for s in range(1,9) for l in range(48)}
    return inp,oracle,tokens,hashes

def args_for(binary,out,context,mode,controller,compiler,mini=False):
    a=pp.parser().parse_args(['--binary',str(binary),'--output',str(out),'--context',str(context),
        '--tokens','8','--seconds','172800','--wait-seconds','7200','--controller',controller,
        '--draft','script' if mode in ('hit','miss') else mode]+(['--mini'] if mini else []))
    a.host_memory='resident' if mini else 'layer-streaming'
    a.host_path='prepared';a.argument_audit=compiler=='gnu-host'
    a.dispatch=P/('dispatch-all-new.json' if mini else 'dispatch-p38.json')
    return a

def script_for(path,mode,tokens,vocab):
    if mode not in ('hit','miss'):return None
    guesses=tokens[:7] if mode=='hit' else [(t+1)%vocab for t in tokens[:7]]
    path.write_text(' '.join(map(str,guesses))+'\n');return path

def mini_request(args,watch,prompt):
    # Real Engine and prepared launches, with a 31-token prompt overriding the
    # generic five-token mini convenience entry. No mocked ranks or fixtures.
    args.output.mkdir(parents=True);transport=None
    try:
        transport=pp.Transport.__new__(pp.Transport)
        transport.__init__(args,args.output,check=watch.check,launch_hook=watch.launch)
        guesses=list(map(int,args.script.read_text().split())) if args.script else []
        result=pp.request_run(transport,pp.Draft(args.draft,guesses),prompt,8,(),True,False)
        for rank in (0,1):transport.call(rank,pp.DUMP,position=2147483647)
        transport.close(True);transport=None
        result.update(passed=True,device_executed=False,no_speed_claim=True)
        save(args.output/'receipt.json',result);return result
    except BaseException as error:
        save(args.output/'receipt.json',dict(passed=False,device_executed=False,error=str(error)))
        if transport is not None and hasattr(transport,'stop_write'):
            transport.stop(error);transport.close(False)
        raise

def run_case(case,compiler,binary,sources,ledger):
    mini=case['phase']=='rollback';context=case['context'];mode=case['mode'];controller=case['controller']
    entry=case.get('entry');inp=oracle=None;want_tokens=want_fixtures=None
    if entry:inp,oracle,want_tokens,want_fixtures=expected(entry)
    identity=dict(case={k:v for k,v in case.items() if k!='entry'},compiler=compiler,
        binary_sha256=storage.digest(binary),source_sha256=sources,
        manifest_sha256=storage.digest(MANIFEST),oracle_tokens=want_tokens,oracle_fixtures=want_fixtures)
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    previous=next((r for r in ledger['rows'] if r.get('key')==key and r.get('passed')),None)
    if previous:
        archive=previous.get('archive')
        if not archive and previous.get('scratch_retained') and Path(previous['scratch_retained']).exists():
            previous['archive']=archive=storage.discard(Path(previous['scratch_retained']));save(LEDGER,ledger)
        pp.require(archive and storage.digest(P/archive['path'])==archive['sha256'],'cached pass missing verified archive')
        print('REUSE',compiler,case['name'],flush=True);return previous
    admission=admit(context,mini);root=B/f'capacity-{compiler}-{case["name"]}-{key[:12]}-{time.time_ns()}'
    root.mkdir();out=root/'run';watch=MemoryWatch();started=time.monotonic()
    row=dict(key=key,identity=identity,passed=False,device_executed=False,no_speed_claim=True,
             case=case['name'],phase=case['phase'],compiler=compiler,capacity=context,mode=mode,controller=controller,admission=admission)
    receipt=P/'evidence'/'capacity-cpu'/f'{key}.json'
    try:
        a=args_for(binary,out,context,mode,controller,compiler,mini);a.input=inp;a.oracle=oracle
        if mini:
            base=next((r for r in reversed(ledger['rows']) if r.get('passed') and r.get('phase')=='rollback' and r.get('compiler')==compiler and r.get('mode')=='none' and r['identity']['binary_sha256']==identity['binary_sha256'] and r['identity']['source_sha256']==sources),None)
            if mode!='none':pp.require(base is not None,'rollback baseline must run first')
            if base is not None:want_tokens=base['tokens'];want_fixtures=base['fixture_sha256']
            a.script=script_for(root/'script.txt',mode,want_tokens or [],16)
            result=mini_request(a,watch,([2,5,3,7,1]*7)[:31]);observed=fixtures(out,4)
        else:
            a.script=script_for(root/'script.txt',mode,want_tokens,248320)
            result=pp.run(a,check=watch.check,launch_hook=watch.launch);observed=fixtures(out,48)
        pp.require(result.get('passed') and not result.get('device_executed',False),'CPU request receipt')
        pp.require(len(result['tokens'])==8,'eight output tokens required')
        if want_tokens is not None:pp.require(result['tokens']==want_tokens,'oracle/generated tokens differ')
        if want_fixtures is not None:pp.require(observed==want_fixtures,'oracle/cross-mode retained layer bytes differ')
        if mode=='hit':pp.require(result['stats']['hits']==7 and result['stats']['misses']==0,'all-hit script not exercised')
        if mode=='miss':pp.require(result['stats']['misses']==7 and result['stats']['hits']==0,'all-miss script not exercised')
        boundary=False
        if mini and mode=='miss':
            trace=result['rank_trace']
            for j,t in enumerate(trace):
                if t['rank']==0 and t['op']==pp.HALF and t['position']==32 and t.get('speculative'):
                    resolution=next((x for x in trace[j+1:] if x['rank']==0 and x['op'] in (pp.ACCEPT,pp.ROLLBACK)),None)
                    boundary=resolution is not None and resolution['op']==pp.ROLLBACK
            pp.require(boundary,'no discarded speculative half across the 32-position boundary')
            timing_rows=[json.loads(line) for line in (out/'rank0/timings.jsonl').read_text().splitlines()]
            crossing=[t for t in timing_rows if t.get('position')==32 and t.get('speculative')]
            pp.require(crossing and all(t.get('launch_extent')==64 and t.get('capacity_reprepares',0)>0 for t in crossing),'no proven prepared-launch boundary at speculative position 32')
            row['boundary_timing_rows']=crossing
        row.update(passed=True,tokens=result['tokens'],token_matches=8,layer_matches=len(observed),fixture_sha256=observed,
                   stats=result['stats'],boundary_32_discarded=boundary,host_memory=a.host_memory,
                   argument_audit=a.argument_audit,peak_aggregate_rss_anon_bytes=watch.peak,seconds=time.monotonic()-started,
                   pipeline_receipt_sha256=storage.digest(out/'receipt.json'))
        # Qualification is written before destructive fixture retention.
        save(receipt,row)
        try:row['archive']=storage.discard(root)
        except Exception as retention:row['retention_error']=str(retention);row['scratch_retained']=str(root)
        save(receipt,row)
    except BaseException as error:
        row.update(passed=False,error=str(error),seconds=time.monotonic()-started,peak_aggregate_rss_anon_bytes=watch.peak)
        save(receipt,row)
        if root.exists():
            try:row['archive']=storage.discard(root);save(receipt,row)
            except Exception as retention:row['retention_error']=str(retention);save(receipt,row)
        ledger['rows'].append(row);save(LEDGER,ledger);raise
    ledger['rows'].append(row);save(LEDGER,ledger)
    print('PASS',compiler,case['name'],len(observed),'fixtures',flush=True);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=('all','suite','modes','rollback'),default='all')
    ap.add_argument('--compiler',choices=('both','gnu-host','icpx-host'),default='both')
    ap.add_argument('--case',help='optional exact case name; partial campaigns never pass the full gate')
    ap.add_argument('--list',action='store_true',help='read-only preregistration; do not execute binaries')
    options=ap.parse_args();manifest=json.loads(MANIFEST.read_text());chosen,development=entries(manifest)
    cases=[]
    for entry in chosen:
        for context in (256,4096,32768):cases.append(dict(name=f'suite-{entry["prompt_id"]}-{context}',phase='suite',context=context,mode='none',controller='native',entry=entry))
    for mode in ('none','hit','miss','mtp'):cases.append(dict(name=f'development-4096-{mode}',phase='modes',context=4096,mode=mode,controller='native',entry=development))
    for controller in ('python','native'):
        for mode in ('none','hit','miss'):cases.append(dict(name=f'rollback-4096-{controller}-{mode}',phase='rollback',context=4096,mode=mode,controller=controller))
    selected=[c for c in cases if (options.phase=='all' or c['phase']==options.phase) and (not options.case or c['name']==options.case)]
    pp.require(selected,'no matching gate cases')
    compilers=('gnu-host','icpx-host') if options.compiler=='both' else (options.compiler,)
    if options.list:
        print(json.dumps(dict(compilers=compilers,cases=[{k:v for k,v in c.items() if k!='entry'} for c in selected],device_executed=False),indent=2));return
    pp.require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2','nice19 and OMP_NUM_THREADS=2 required')
    B.mkdir(exist_ok=True)
    lock=(B/'capacity-cpu.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=json.loads(LEDGER.read_text()) if LEDGER.exists() else dict(schema='packet44.capacity-cpu.v1',passed=False,device_executed=False,no_speed_claim=True,rows=[])
    ledger['passed']=False;sources=source_identity();completed=[]
    for compiler in compilers:
        binary=B/compiler/'own-rt-iq3';host_binary(binary)
        for case in selected:completed.append(run_case(case,compiler,binary,sources,ledger))
    # A short prefix matches the same frozen oracle independently at all three
    # capacities. Keep the explicit cross-capacity comparison in the receipt.
    cross=[]
    for compiler in compilers:
        for entry in chosen:
            rows=[r for r in completed if r['compiler']==compiler and r['phase']=='suite' and r['identity']['case']['name'].startswith('suite-'+entry['prompt_id']+'-')]
            if len(rows)==3:
                pp.require(all((r['tokens'],r['fixture_sha256'])==(rows[0]['tokens'],rows[0]['fixture_sha256']) for r in rows),'cross-capacity fixture difference')
                cross.append(dict(compiler=compiler,prompt_id=entry['prompt_id'],capacities=[r['capacity'] for r in rows],token_matches=8,layer_matches=384,passed=True))
    ledger.update(passed=options.phase=='all' and options.compiler=='both' and not options.case and len(completed)==38,
                  latest_invocation_passed=True,latest_invocation_cases=len(completed),cross_capacity=cross,
                  selected_suite_prompts=[r['prompt_id'] for r in chosen],source_sha256=sources)
    save(LEDGER,ledger)
    print(json.dumps(dict(passed=ledger['passed'],latest_invocation_passed=True,cases=len(completed),cross_capacity=len(cross),device_executed=False)))
if __name__=='__main__':main()
