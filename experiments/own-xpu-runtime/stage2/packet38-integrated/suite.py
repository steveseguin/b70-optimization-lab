#!/usr/bin/env python3
"""Persistent rank suite driver; an exactness failure is recorded and does not skip requests."""
import copy, gzip, hashlib, json, math, os, signal, statistics, time, types
from pathlib import Path
import pipeline
import storage
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
RESET=11
CHECKER=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite/suite_check.py'
EOS=(248044,248046)

def select_warmup(prompts,context,vocab):
    """A short synthetic request absent from every contiguous suite input span.

    Capacity/budget/dense geometry select compiled kernels; active position is
    runtime data. Five input positions cross the four-position QSA pooling
    boundary and exercise both target banks. Two requested outputs reach the
    target and (when enabled) draft output heads; no measured prompt is warmed.
    """
    length=5;alphabet=15
    pipeline.require(context>=length+1 and vocab>alphabet,'warmup context/vocabulary bounds')
    prompts=[tuple(p) for p in prompts]
    pipeline.require(prompts and all(p for p in prompts),'warmup needs nonempty admitted prompts')
    spans={p[start:start+length] for p in prompts for start in range(max(0,len(p)-length+1))}
    seed=0
    for token in (2,5,3,7,1):seed=seed*alphabet+token-1
    space=alphabet**length
    pipeline.require(len(spans)<space,'warmup candidate space exhausted')
    # At most len(spans) distinct candidates are blocked, so this bound always
    # finds one without an unbounded search. Candidate tokens exclude EOS IDs.
    for offset in range(len(spans)+1):
        value=(seed+offset)%space;tokens=[0]*length
        for index in range(length-1,-1,-1):tokens[index]=value%alphabet+1;value//=alphabet
        if tuple(tokens) not in spans:
            pipeline.require(tuple(tokens) not in prompts,'warmup repeats suite prompt')
            return tokens
    raise AssertionError('warmup selection bound')

def checker_module(path=CHECKER):
    # Hash and execute the same immutable byte snapshot: another producer may
    # update the read-only external source after this load. Never hash it later.
    source=path.read_bytes();module=types.ModuleType('packet38_readonly_suite_checker')
    module.__file__=str(path)
    exec(compile(source,str(path),'exec'),module.__dict__)
    module.source_sha256=hashlib.sha256(source).hexdigest()
    return module

def retained_state(root):
    """Exact hashes and metadata survive removal of disposable state snapshots."""
    archive=Path(root)/'state-evidence.json.gz'
    record=json.loads(gzip.decompress(archive.read_bytes()))
    pipeline.require(record['schema']=='packet38.request-state-evidence.v1','state archive schema')
    pipeline.require(len({r['path'] for r in record['files']})==len(record['files']),'duplicate state evidence')
    for row in record['files']:
        pipeline.require(len(row['sha256'])==64 and row['bytes']>=0,'invalid state evidence hash')
        if 'text' in row:
            raw=row['text'].encode()
            pipeline.require(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'retained state metadata changed')
    return {r['path']:r for r in record['files']}

def retain_request_state(root):
    """Hash complete state before deletion; retain all eight layer fixtures raw."""
    root=Path(root);files=[]
    for rank in (0,1):
        base=root/f'rank{rank}'
        for directory in sorted(base.glob('state-*')):
            if directory.is_dir():files.extend(f for f in directory.rglob('*') if f.is_file())
        draft=base/'draft-final-state'
        if draft.is_dir():files.extend(f for f in draft.rglob('*') if f.is_file())
        inventory=base/'request-state-inventory.json'
        if inventory.is_file():files.append(inventory)
    rows=[]
    for file in sorted(files):
        h=hashlib.sha256()
        with file.open('rb') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
        row=dict(path=str(file.relative_to(root)),bytes=file.stat().st_size,sha256=h.hexdigest())
        if file.suffix in ('.json','.jsonl'):row['text']=file.read_text()
        rows.append(row)
    pipeline.require(rows,'missing request state before retention')
    by_path={r['path']:r for r in rows}
    # Verify the runtime's recorded target hashes before trusting or deleting bytes.
    for row in rows:
        if row['path'].endswith('/state.json'):
            metadata=json.loads(row['text']);directory=Path(row['path']).parent
            for name,expected in metadata['buffers'].items():
                leaf=('alternate-'+name[len('alternate:'):] if name.startswith('alternate:') else name)+'.bin'
                pipeline.require(by_path[str(directory/leaf)]['sha256']==expected,'target state recorded hash mismatch')
    raw=json.dumps(dict(schema='packet38.request-state-evidence.v1',files=rows),sort_keys=True,separators=(',',':')).encode()
    packed=gzip.compress(raw,mtime=0)
    storage.admit(len(packed)+1_000_000)
    archive=root/'state-evidence.json.gz';temporary=root/'state-evidence.json.gz.tmp'
    temporary.write_bytes(packed)
    pipeline.require(gzip.decompress(temporary.read_bytes())==raw,'state retention gzip roundtrip')
    temporary.replace(archive)
    pipeline.require(retained_state(root)==by_path,'state retention verification')
    for file in files:file.unlink()
    return dict(files=len(rows),original_bytes=sum(r['bytes'] for r in rows),retained_bytes=len(packed),sha256=pipeline.sha(archive))

def reset(transport,destination,oracle=None):
    pipeline.require(not any(transport.pending),'reset with pending commands')
    # RESET writes the previous request's state before opening the next output.
    # At most one such raw snapshot survives, and no retained fixture is removed.
    storage.admit(8_000_000 if transport.a.mini else 550_000_000)
    previous=getattr(transport,'request_output',transport.out)
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    for rank in (0,1):
        metadata=transport.out/f'rank{rank}'/f'reset-{transport.seq[rank]+1}.txt'
        output=destination/f'rank{rank}'
        pipeline.require('\n' not in str(output) and (oracle is None or '\n' not in str(oracle)),'newline in reset path')
        metadata.write_text(str(output)+'\n'+(str(oracle.resolve()) if oracle else '')+'\n')
        transport.call(rank,RESET)
    retained=retain_request_state(previous)
    pipeline.save(previous/'state-retention.json',retained)
    transport.request_output=destination
    transport.mapping[:pipeline.SHARED]=bytes(pipeline.SHARED)
    transport.trace=[]
    transport.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
    transport.last_complete=[0.,0.]

def rate(result,device):
    rows=result.get('timing_rows',[])
    if rows and rows[-1]['token_id'] in EOS:rows=rows[:-1]
    if not device or result.get('diagnostic') or len(rows)<2:return None
    elapsed=rows[-1]['completed_monotonic']-rows[0]['completed_monotonic']
    return (len(rows)-1)/elapsed if elapsed>0 else None

def summarize(rows,complete,expected=12):
    def median(values):
        good=[v for v in values if isinstance(v,(int,float)) and math.isfinite(v) and v>0]
        return statistics.median(good) if good else None
    valid=[r for r in rows if r.get('passed')]
    repeats=sorted({r['repeat'] for r in rows})
    return dict(schema='packet38.suite.v1',passed=bool(rows) and all(r.get('passed') for r in rows),
                complete=bool(complete),expected_prompts=expected,rows=rows,
                decode_median_tok_s=median(r.get('decode_tok_s') for r in valid),
                repeat_decode_medians={str(n):median(r.get('decode_tok_s') for r in valid if r['repeat']==n) for n in repeats},
                median_definition='ordinary median of all successful finite positive per-request rates across prompts and repeats; failed/missing/zero rates excluded; never pool distinct windows',
                decode_definition='(N-1)/(completion_time[N]-completion_time[1]), N non-EOG emitted tokens, at most 64; 63 intervals for 64 tokens',
                no_speed_claim=True)

def collect_fixtures(output,count,mini=False):
    layers=4 if mini else 48
    for step in range(1,min(count,8)+1):
        dest=output/f'step{step}';dest.mkdir(exist_ok=True);records=[]
        for layer in range(layers):
            name=f'layer-{layer:02}.bf16'
            rank=0 if layer<(2 if mini else 24) else 1
            source=output/f'rank{rank}'/f'step{step}'/name
            pipeline.require(source.is_file(),f'missing retained fixture {source}')
            target=dest/name
            if not target.exists():os.link(source,target)
            records.append(dict(layer=layer,shape=[1,4,16 if mini else 2560],dtype='BF16 little-endian',sha256=pipeline.sha(target)))
        (dest/'layers.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in records))

def run_request(transport,args,prompt,count,*,kernel_warmup=False):
    storage.admit(8_000_000 if args.mini else 32_000_000)
    provider=pipeline.Draft(args.draft,list(map(int,args.script.read_text().split())) if args.script else [])
    # EOS termination is disabled only for the excluded synthetic warmup. Two
    # outputs must run even if its first target token happens to be EOS, so the
    # draft decode/output-head path executes before any measured request.
    eos=() if args.mini or kernel_warmup else EOS
    result=pipeline.request_run(transport,provider,prompt,count,eos,args.prompt_overlap=='on',args.dump_state)
    if kernel_warmup:pipeline.require(count==2 and len(result['tokens'])==2,'incomplete kernel warmup')
    result['rank_trace']=copy.deepcopy(transport.trace);result['rank_metrics']=copy.deepcopy(transport.metrics)
    result.update(schema='own-runtime.iq3.packet26.run.v1',arithmetic='iq3-p17-detmath-v2',passed=True,
                  device_executed=args.device,draft=args.draft,controller=getattr(args,'controller','python'),
                  binary_sha256=pipeline.sha(args.binary),no_speed_claim=True)
    if args.timing=='class':result.update(diagnostic=True,evidence_label='DIAGNOSTIC ONLY: per-class profiling')
    result['decode_tok_s']=rate(result,args.device)
    elapsed=(transport.work_end-transport.work_start)*1000
    for m in result['rank_metrics']:
        m['idle_and_coordination_ms']=max(0.,elapsed-m['busy_ms'])
    return result

def compare_request(output,result,entry,compare):
    """Exactness is a request outcome, not a rank-execution exception."""
    try:
        if compare:
            n,f=compare.check_prompt(output,ROOT/entry['oracle_directory'],entry,ROOT)
            result['oracle_check']=dict(passed=True,tokens=n,fixture_files=f,checker_sha256=compare.source_sha256)
    except (OSError,ValueError,KeyError,TypeError) as error:
        result.update(passed=False,exactness_error=str(error))
    return result

def admit_inputs(entries,output,compare):
    """Freeze admitted metadata and enforce one immutable model/plan per launch."""
    snapshots={};identities=[];first=None
    required={'tokens.txt','input.json','identity.tsv','plan.tsv','vocab.bin'}
    for entry in entries:
        bundle=ROOT/entry['input_bundle'];destination=output/'input-bundles'/entry['prompt_id']
        pipeline.require(set(entry['input_bundle_hashes'])==required,'bundle hash coverage')
        destination.mkdir(parents=True)
        blobs={name:(bundle/name).read_bytes() for name in sorted(required)}
        hashes={name:hashlib.sha256(value).hexdigest() for name,value in blobs.items()}
        pipeline.require(hashes==entry['input_bundle_hashes'],'input bundle changed before admission')
        inp=json.loads(blobs['input.json']);tokens=list(map(int,blobs['tokens.txt'].split()))
        pipeline.require(inp['tokens']==tokens and len(tokens)==entry['prompt_tokens'],'prompt input token binding')
        identity=(hashes['plan.tsv'],hashes['identity.tsv'],inp['model_dir'])
        if first is None:first=identity
        pipeline.require(identity==first,'suite model/plan identity differs between requests')
        # Reuse the actual checker for its complete manifest/input/oracle binding.
        oracle=ROOT/entry['oracle_directory'];compare.check_prompt(oracle,oracle,entry,ROOT)
        for name,data in blobs.items():(destination/name).write_bytes(data)
        snapshots[entry['prompt_id']]=(destination,tokens)
        identities.append(dict(prompt_id=entry['prompt_id'],model_dir=inp['model_dir'],input_bundle_hashes=hashes))
    pipeline.save(output/'input-admission.json',dict(passed=True,checker_sha256=compare.source_sha256,
                  one_model_plan_identity=True,inputs=identities))
    return snapshots

def run(args,environment=None,check=None,failure_hook=None,launch_hook=None):
    pipeline.require(os.getpriority(os.PRIO_PROCESS,0)==args.native_nice,'declared priority mismatch')
    pipeline.require(os.environ.get('OMP_NUM_THREADS')=='2','OMP_NUM_THREADS=2 required')
    pipeline.require(args.repeat>0 and args.repeat<=100,'repeat bound 1..100')
    pipeline.require(not args.output.exists(),'new suite output required')
    manifest_bytes=args.suite_manifest.read_bytes();manifest=json.loads(manifest_bytes);entries=manifest['prompts']
    pipeline.require(entries and len({e['prompt_id'] for e in entries})==len(entries),'empty/duplicate suite')
    pipeline.require(manifest['arithmetic']=='iq3-p17-detmath-v2' and manifest['token_cap']==64,'suite identity')
    pipeline.require(all(Path(e['prompt_id']).name==e['prompt_id'] and e['prompt_id'] not in ('.','..') for e in entries),'unsafe prompt id')
    args.output.mkdir(parents=True);(args.output/'suite-manifest.snapshot.json').write_bytes(manifest_bytes);ranks=args.output/'ranks';ranks.mkdir()
    compare=checker_module() if not args.mini else None
    snapshots=admit_inputs(entries,args.output,compare) if compare else {}
    launch=copy.copy(args);launch.input=(snapshots[entries[0]['prompt_id']][0] if compare else ROOT/entries[0]['input_bundle']);launch.oracle=None;launch.tokens=64
    pipeline.require(args.context>=manifest['context'],'suite context admission')
    transport=None;rows=[];failure=None;stopped=[]
    old={s:signal.signal(s,lambda signum,frame:stopped.append(signum)) for s in (signal.SIGTERM,signal.SIGINT)}
    def check_all():
        pipeline.require(not stopped,'coordinator stop requested')
        if check:check()
    try:
        transport=pipeline.Transport.__new__(pipeline.Transport)
        transport.__init__(launch,ranks,environment,check_all,launch_hook)
        if failure_hook:transport.failure_hook=failure_hook
        warm=args.output/'warmup';reset(transport,warm)
        measured_prompts=[entry['mini_tokens'] if args.mini else snapshots[entry['prompt_id']][1] for entry in entries]
        warm_prompt=select_warmup(measured_prompts,args.context,16 if args.mini else 248320)
        warm_result=run_request(transport,args,warm_prompt,2,kernel_warmup=True)
        warm_result['excluded_from_timing']=True
        warm_result['warmup_selection']=dict(schema='packet38.distinct-kernel-warmup.v1',
            token_ids=warm_prompt,prompt_tokens=len(warm_prompt),requested_output_tokens=2,
            eos_termination_disabled_only_for_excluded_warmup=True,completed_output_tokens=len(warm_result['tokens']),
            token_sha256=hashlib.sha256(json.dumps(warm_prompt,separators=(',',':')).encode()).hexdigest(),
            distinct_from_every_suite_prompt=True,absent_from_every_contiguous_suite_input_span=True,
            suite_prompt_count=len(measured_prompts),complete_reset_before_measured_requests=True,
            kernel_scope='same fixed capacity/budget/dense geometry; active position is runtime data; five inputs cross QSA pooling boundary and both target banks; output heads execute before any timed request')
        warm_result['first_position_ms_by_rank']=[next((r['busy_ms'] for r in transport.trace if r['rank']==rank and r['op']==pipeline.HALF),None) for rank in (0,1)]
        pipeline.save(warm/'receipt.json',warm_result)
        for repeat in range(1,args.repeat+1):
            for entry in entries:
                output=args.output/f'repeat-{repeat}'/entry['prompt_id']
                reset(transport,output)
                prompt=entry.get('mini_tokens') if args.mini else snapshots[entry['prompt_id']][1]
                count=entry.get('mini_count',64) if args.mini else 64
                pipeline.require(len(prompt)+count-1<=args.context,'request context exceeded')
                result=run_request(transport,args,prompt,count)
                collect_fixtures(output,len(result['tokens']),args.mini)
                result.update(prompt_id=entry['prompt_id'],repeat=repeat,ended_early=len(result['tokens'])<count,
                              first_position_ms_by_rank=[next((r['busy_ms'] for r in transport.trace if r['rank']==rank and r['op']==pipeline.HALF),None) for rank in (0,1)])
                pipeline.save(output/'receipt.json',result)
                compare_request(output,result,entry,compare)
                pipeline.save(output/'receipt.json',result)
                rows.append(dict(prompt_id=entry['prompt_id'],repeat=repeat,passed=result['passed'],tokens=len(result['tokens']),
                                 decode_tok_s=result['decode_tok_s'],prompt_wall_ms=result['prompt_wall_ms'],acceptance=result['acceptance'],
                                 receipt=str((output/'receipt.json').relative_to(args.output)),error=result.get('exactness_error')))
                pipeline.save(args.output/'summary.json',summarize(rows,manifest.get('complete',False)))
        # Final reset retains the last request's complete state before FINISH.
        reset(transport,args.output/'after-suite')
        transport.close(True)
    except Exception as error:
        failure=error
        diagnostic_errors=[]
        pipeline.failure_attempt("suite failure receipt",lambda:pipeline.save(args.output/'failure-before-teardown.json',dict(passed=False,error=str(error),rows=rows)),diagnostic_errors)
        if failure_hook:pipeline.failure_attempt("suite failure hook",lambda:failure_hook(error),diagnostic_errors)
        if transport is not None and hasattr(transport,'stop_write'):
            try:transport.stop(error)
            finally:
                try:transport.close(False)
                except Exception as teardown:
                    teardown_message=str(teardown)
                    pipeline.failure_attempt("suite teardown receipt",lambda:pipeline.save(args.output/'teardown-error.json',dict(error=teardown_message)),diagnostic_errors)
    finally:
        for sig,handler in old.items():signal.signal(sig,handler)
    summary=summarize(rows,manifest.get('complete',False));summary.update(device_executed=args.device,controller=getattr(args,'controller','python'),draft=args.draft,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),same_rank_processes=True,
        evidence_label='official draft head, draft-only 8-bit requantisation, output identical to sequential decode' if args.draft=='mtp' else 'sequential target decode')
    if failure:summary.update(passed=False,error=str(failure))
    pipeline.save(args.output/'summary.json',summary);pipeline.save(args.output/'receipt.json',summary)
    if failure:raise failure
    return summary

def parser():
    p=pipeline.parser()
    if not any(a.dest=='controller' for a in p._actions):p.add_argument('--controller',choices=('python','native'),default='python')
    if not any(a.dest=='suite_manifest' for a in p._actions):p.add_argument('--suite-manifest',type=Path,required=True)
    if not any(a.dest=='repeat' for a in p._actions):p.add_argument('--repeat',type=int,default=1)
    return p
if __name__=='__main__':
    args=parser().parse_args();pipeline.require(not args.device,'device suite requires admitted window.py')
    raise SystemExit(0 if run(args)['passed'] else 1)
