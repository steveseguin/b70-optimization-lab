#!/usr/bin/env python3
"""Coordinator-only route diagnostic. No launch at import; no automatic retry."""
import argparse,fcntl,gzip,hashlib,importlib.util,json,os,shutil,signal,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;PACKET=P.parent;BASE=P.parents[1]/'packet49c-round2';ROOT=P.parents[4]
sys.path.insert(0,str(BASE))
import pipeline as pp
from window_safety import memory_snapshot
# Import the new shared passive card/fault/fence helpers, never execute a window.
sys.path.insert(0,str(PACKET/'h2d'))
spec=importlib.util.spec_from_file_location('packet55_h2d_safety',PACKET/'h2d/window.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
S=H.S;require=pp.require;save=pp.save;sha=pp.sha
MODEL='/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS'


def build_gate():
    spec=importlib.util.spec_from_file_location('packet55_route_source_gate',P/'source_gate.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate);gate.check()
    row=json.loads((P/'build/device/build-receipt.json').read_text())
    require(row.get('device_executed') is False and row.get('mode')=='device','native build missing')
    require(row['binary_sha256']==sha(P/'build/device/own-rt-iq3'),'diagnostic binary changed')
    for name,digest in row['overlay_sha256'].items():require(sha(P/name)==digest,'overlay changed after compile')
    for name,digest in row['base_checked_sha256'].items():require(sha(ROOT/name)==digest,'parent checked source changed')
    return row


def archive_snapshots(root):
    """Lossless gzip with a full restore-hash check before replacing owned raw files."""
    rows=[]
    for rank in (0,1):
        base=root/f'rank{rank}'
        directories=list(base.glob('state-*'))+[base/'draft-final-state']
        for directory in directories:
            if not directory.is_dir():continue
            for path in sorted(directory.rglob('*.bin')):
                size=path.stat().st_size;digest=sha(path);dest=path.with_suffix(path.suffix+'.gz')
                require(not dest.exists(),'snapshot archive exists')
                with path.open('rb') as source,gzip.open(dest,'wb',compresslevel=1) as sink:shutil.copyfileobj(source,sink,1024**2)
                with gzip.open(dest,'rb') as restore:actual=hashlib.file_digest(restore,'sha256').hexdigest()
                require(actual==digest,'snapshot gzip roundtrip failed')
                rows.append(dict(path=str(path.relative_to(root)),bytes=size,sha256=digest,gzip_sha256=sha(dest)))
                path.unlink()
    if rows:save(root/'snapshot-retention.json',dict(schema='packet55.lossless-snapshots.v1',files=rows))


def reset(transport,destination):
    require(not any(transport.pending),'pending request at reset')
    previous=getattr(transport,'request_output',transport.out)
    destination.mkdir(parents=True)
    for rank in (0,1):
        metadata=transport.out/f'rank{rank}'/f'reset-{transport.seq[rank]+1}.txt'
        metadata.write_text(str(destination/f'rank{rank}')+'\n\n')
        transport.call(rank,11)
    archive_snapshots(previous)
    transport.request_output=destination
    transport.mapping[:pp.SHARED]=bytes(pp.SHARED);transport.trace=[]
    transport.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)];transport.last_complete=[0.,0.]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--faults-reviewed-through',required=True)
    parser.add_argument('--authorized-device-window',action='store_true')
    parser.add_argument('--allow-existing-p49c-draft',action='store_true',help='Requires owner allowance for existing hash-bound official MTP source outside IQ3 directory')
    a=parser.parse_args()
    require(a.authorized_device_window,'coordinator authorization required')
    require(a.allow_existing_p49c_draft,'owner must allow existing packet49c official MTP source; no draft in admitted IQ3 directory')
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(os.sched_getaffinity(0)<=set(range(4,16))|set(range(20,32)),'preparation CPU set required')
    cgroup=Path('/proc/self/cgroup').read_text();require('packet55-' in cgroup and '.service' in cgroup,'coordinator packet55-* unit required')
    out=a.output.resolve();require(out.is_relative_to((P/'evidence').resolve()) and not out.exists(),'fresh route/evidence directory required')
    out.mkdir(parents=True)
    build=build_gate();env=S.environment_gate();env['OMP_NUM_THREADS']='2'
    # Closed native environment. No device masks: native checks actual card2/3 PCI.
    for name in ('ONEAPI_DEVICE_SELECTOR','ZE_AFFINITY_MASK','SYCL_DEVICE_FILTER'):require(not os.environ.get(name),'device mask refused')
    manifest=json.loads((P/'build/calibration-tokenized.json').read_text())
    require(manifest['source_sha256']==sha(P/'calibration-prompts.json') and manifest['model_dir']==MODEL,'calibration identity')
    require(len(manifest['prompts'])==24 and manifest['token_cap']==256,'calibration scope')
    save(out/'calibration-manifest.json',manifest)
    record=dict(schema='packet55.route-window.v1',passed=False,device_executed=False,no_speed_claim=True,
                build_sha256=sha(P/'build/device/build-receipt.json'),binary_sha256=build['binary_sha256'],
                cards=[2,3],pci=[H.PCI[2],H.PCI[3]],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                started_utc_ns=time.time_ns(),requests=[],stop_reasons=[],draft_source='/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8',
                draft_manifest_sha256=sha(BASE/'mtp-manifest.tsv'),draft_source_owner_allowance=True)
    latch=PACKET/('fault-'+record['boot_id']+'.json');transport=None;cursor=None;last_poll=0.;deadline=time.monotonic()+14400
    def persist():save(out/'window.json',record)
    def fault(reason):save(latch,dict(reason=str(reason),output=str(out),boot_id=record['boot_id']))
    def check():
        nonlocal cursor,last_poll
        if time.monotonic()-last_poll>=.25:
            fresh,cursor=S.journal(cursor);last_poll=time.monotonic()
            with (out/'kernel-window.jsonl').open('a') as f:f.write(fresh)
            if S.FAULT.search(fresh):fault('new GPU fault');raise ValueError('new GPU fault; stop without retry')
        require(not record['stop_reasons'],'coordinator stop requested')
        require(time.monotonic()<deadline,'route window deadline')
        require(shutil.disk_usage(out).free>=8_000_000_000,'8GB root free floor')
    handlers={}
    persist()
    try:
        with (PACKET/'window.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            require(not latch.exists(),'packet55 fault latch requires coordinator recovery')
            record['fenced_memory_blocks']=H.memory_fence()
            record['clients']={str(c):H.selected_clients(c) for c in (2,3)}
            sample=memory_snapshot();record['memory_admission']=sample
            require(sample['MemAvailable']>=97*1024**3,'97GiB available before resident ranks required; disjoint cards alone are insufficient')
            require(shutil.disk_usage(out).free>=10_000_000_000,'10GB free before snapshot/route collection required')
            review,through=S.fault_review(a.faults_reviewed_through,time.time_ns()//1000);record['fault_review']=review
            initial,cursor=S.journal();(out/'kernel-boot-before-review.jsonl').write_text(initial)
            fresh,cursor=S.journal(cursor,since_us=through);(out/'kernel-before.jsonl').write_text(fresh)
            require(not S.FAULT.search(fresh),'unreviewed GPU fault; coordinator recovery required')
            record['ldd']=S.ldd_preflight(P/'build/device/own-rt-iq3',env)
            runtime=P/'build/runtime';runtime.mkdir(exist_ok=True)
            (runtime/'memory-plan.json').write_bytes((BASE/'memory-plan.json').read_bytes())
            pp.P=runtime  # Own driver-cache, never write through the sealed packet.
            args=pp.parser().parse_args(['--binary',str(P/'build/device/own-rt-iq3'),'--output',str(out/'owners'),
                    '--input',str(P/'build/input'),'--dispatch',str(BASE/'dispatch-speed6.json'),'--device',
                    '--card','2','--context','4096','--draft','mtp','--draft-rank','1','--target-split','23',
                    '--seconds','14400','--wait-seconds','600','--max-new','256','--retain-steps','none','--controller','native'])
            args.output.mkdir()
            handlers={sig:signal.signal(sig,lambda n,f:record['stop_reasons'].append('coordinator signal '+str(n))) for sig in (signal.SIGTERM,signal.SIGINT)}
            transport=pp.Transport.__new__(pp.Transport)
            def launched(pid):record['device_executed']=True;record.setdefault('owner_pids',[]).append(pid);persist()
            transport.__init__(args,args.output,environment=env,check=check,launch_hook=launched)
            transport.failure_hook=lambda reason:fault(reason) if getattr(reason,'device_owner_failed',False) else None
            # A benchmark sanity prompt is isolated from cache training and output.
            suite=json.loads((BASE/'oracle/results/suite-manifest.json').read_text());entry=suite['prompts'][0]
            oracle=ROOT/entry['oracle_directory'];oracle_result=json.loads((oracle/'result.json').read_text())
            require(suite['arithmetic']==oracle_result['arithmetic']=='iq3-p49-split32-v1','sanity arithmetic identity')
            record['oracle_suite_manifest_sha256']=sha(BASE/'oracle/results/suite-manifest.json')
            require(sha(oracle/'receipt.json')==entry['oracle_receipt_sha256'],'sanity oracle receipt changed')
            oracle_receipt=json.loads((oracle/'receipt.json').read_text())
            require(sha(oracle/'result.json')==oracle_receipt['result_sha256'],'sanity oracle token hash changed')
            sanity=dict(prompt_id='sanity-'+entry['prompt_id'],tokens=json.loads((oracle/'input.json').read_text())['tokens'],max_new_tokens=128)
            prompts=[sanity]+manifest['prompts']
            for index,prompt in enumerate(prompts):
                check();dest=out/('sanity' if index==0 else 'requests')/prompt['prompt_id'];reset(transport,dest)
                result=pp.request_run(transport,pp.Draft('mtp'),prompt['tokens'],prompt['max_new_tokens'],(248044,248046),True,False)
                # Diagnostic copies perturb elapsed time. Retain tokens/acceptance;
                # strip all rate claims, including inherited summary rates.
                result.update(passed=True,completed=True,prompt_id=prompt['prompt_id'],generated_tokens=len(result['tokens']),
                              no_speed_claim=True,diagnostic=True,evidence_label='route-only diagnostic; D2H synchronizes after every router')
                for name in tuple(result):
                    if 'tok_s' in name or 'rate' in name:result[name]=None
                if index==0:
                    require(result['tokens']==oracle_result['tokens'],'diagnostic tokens differ from packet49 CPU oracle')
                    result['oracle_token_identity']=True;result['oracle_result_sha256']=sha(oracle/'result.json')
                save(dest/'result.json',result)
                record['requests'].append(dict(prompt_id=prompt['prompt_id'],generated_tokens=len(result['tokens']),result_sha256=sha(dest/'result.json')));persist()
            transport.close(True);archive_snapshots(dest)
            # Full five-minute kernel watch, split into bounded polls. No restarts.
            end=time.monotonic()+305
            while time.monotonic()<end:check();time.sleep(.25)
            record.update(passed=True,requested_scope_complete=all(r['generated_tokens']==256 for r in record['requests'][1:]),all_generated_256=all(r['generated_tokens']==256 for r in record['requests'][1:]),finished_utc_ns=time.time_ns());persist();return 0
    except Exception as error:
        record['error']=str(error)
        if transport is not None and hasattr(transport,'stop_write'):
            try:transport.stop(error);transport.close(False)
            except Exception as teardown:record['teardown_error']=str(teardown)
            record['retained_pids']=getattr(transport,'retained',[])
            if record['retained_pids']:fault('live owner retained for coordinator')
        persist();return 75 if record.get('retained_pids') else 1
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)

if __name__=='__main__':raise SystemExit(main())
