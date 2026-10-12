#!/usr/bin/env python3
"""Prepare/run six strictly sequential CPU draft capture arms; never opens a device."""
import argparse,fcntl,gzip,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
from storage import build_size,discard

P=Path(__file__).resolve().parent
B=P/'build'
BASE=P.parent/'packet38-integrated'
NAME='incident-retrospective'
CONTEXTS=(256,4096,32768)
PREFIX=['nice','-n','19','ionice','-c','3']
ROOT_FLOOR=8_000_000_000
BUILD_LIMIT=4_000_000_000
ANON_LIMIT=8_000_000_000
RETAINED_TOKENS=8


def require(ok,message):
    if not ok:raise RuntimeError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def admission(extra):
    result=subprocess.run(PREFIX+['df','-B1','/'],text=True,capture_output=True,check=True)
    free=int(result.stdout.splitlines()[-1].split()[3]);used=build_size(B)
    require(free>=ROOT_FLOOR+extra,f'root free {free} cannot preserve 8 GB floor through {extra}-byte write')
    require(used+extra<BUILD_LIMIT,f'packet build {used}+{extra} exceeds own 4 GB limit')
    return dict(root_free_bytes=free,build_bytes=used,write_reserve_bytes=extra)


def prepare():
    source=BASE/'build'/('captured-'+NAME)
    sealed=json.loads((BASE/('capture-input-'+NAME+'.json')).read_text())
    require(sha(source/'target-rows.json')==sealed['target_rows_sha256'],'source target rows changed')
    require(sha(BASE/'build'/('capture-'+NAME+'.tsv'))==sealed['table_sha256'],'source capture table changed')
    for name,digest in sealed['streams'].items():
        require(Path(name).name==name and sha(source/name)==digest,'source confirmed stream changed: '+name)
    rows=json.loads((source/'target-rows.json').read_text())
    captured_input=json.loads((source/'input.json').read_text())
    prompt_tokens=len(captured_input['tokens']);count=prompt_tokens+RETAINED_TOKENS-1
    require(prompt_tokens==87 and count==94,'development prompt no longer 87 tokens / 94 capture rows')
    require(len(rows)>=count+1,'next confirmed input token missing')
    require([r['position'] for r in rows[:count+1]]==list(range(count+1)),'captured position order changed')
    for j in range(prompt_tokens):require(rows[j]['input_token']==captured_input['tokens'][j],'prompt token disagrees with confirmed rows')
    destination=B/('captured-'+NAME);table=B/('capture-'+NAME+'.tsv')
    admission(count*20480+1_000_000);destination.mkdir(parents=True,exist_ok=True)
    hashes={};lines=[]
    for j in range(count):
        name=f'streams-{j}.bf16';raw=(source/name).read_bytes()
        require(len(raw)==20480 and sha(source/name)==sealed['streams'][name],'stream extent/hash changed')
        dest=destination/name
        if dest.exists():require(dest.read_bytes()==raw,'existing packet44 capture differs')
        else:dest.write_bytes(raw)
        hashes[name]=sha(dest)
        lines.append(f"{j} {rows[j+1]['input_token']} {int(j>=prompt_tokens-2)} {dest.resolve()}")
    table.write_text('\n'.join(lines)+'\n')
    save(destination/'target-rows.json',rows[:count+1]);save(destination/'input.json',captured_input)
    receipt=dict(source=str(source),source_capture_receipt_sha256=sha(BASE/('capture-input-'+NAME+'.json')),
        source_verified_streams=len(sealed['streams']),source_table_sha256=sealed['table_sha256'],
        streams=hashes,table_sha256=sha(table),target_rows_sha256=sha(destination/'target-rows.json'),
        prompt_tokens=prompt_tokens,generated_prefix_tokens=RETAINED_TOKENS,capture_rows=count,
        head_rows=sum(j>=prompt_tokens-2 for j in range(count)),device_executed=False)
    save(P/('capture-input-'+NAME+'.json'),receipt)
    return table,receipt


def host_binary(binary):
    require(binary.is_file(),'host binary missing: '+str(binary))
    result=subprocess.run(PREFIX+['readelf','-d',str(binary)],text=True,capture_output=True,check=True)
    libraries=result.stdout.lower()
    require(not any(x in libraries for x in ('libsycl','libze_loader','libur_loader','libopencl')),'accelerator-linked binary refused')
    require(binary.parent.name in ('gnu-host','icpx-host'),'non-host binary path refused')


def anon(pid):
    try:lines=Path(f'/proc/{pid}/status').read_text().splitlines()
    except FileNotFoundError:return 0
    return sum(int(line.split()[1])*1024 for line in lines if line.startswith('RssAnon:'))


def fixtures(root):
    return {str(f.relative_to(root)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in sorted(root.glob(pattern))}


def compress_log(raw):
    expected=sha(raw);admission(raw.stat().st_size+1_000_000)
    target=raw.with_suffix(raw.suffix+'.gz')
    with raw.open('rb') as source,target.open('wb') as dest:
        with gzip.GzipFile(fileobj=dest,mode='wb',mtime=0) as output:shutil.copyfileobj(source,output,1024*1024)
    h=hashlib.sha256()
    with gzip.open(target,'rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    require(h.hexdigest()==expected,'compressed log differs');raw.unlink()
    return dict(path=str(target.relative_to(P)),sha256=sha(target),uncompressed_sha256=expected)


def run_arm(compiler,context,table):
    binary=B/compiler/'own-rt-iq3';host_binary(binary)
    output=B/(f'draft-reference-c{context}' if compiler=='gnu-host' else f'draft-icpx-c{context}')
    require(not output.exists(),'capture arm already exists; inspect evidence instead of retrying: '+str(output))
    admission(150_000_000)
    input_dir=B/'input';inp=json.loads((input_dir/'input.json').read_text())
    dispatch=P/'dispatch-p38.json'
    command=PREFIX+[str(binary),'--draft-capture',str(table),'--rank','1','--context',str(context),
        '--plan',str(input_dir/'plan.tsv'),'--identity',str(input_dir/'identity.tsv'),
        '--model-dir',inp['model_dir'],'--output',str(output),'--dispatch',str(dispatch)]
    env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    log=B/f'draft-{compiler}-c{context}.log';start=time.monotonic();peak=0;child=None
    with log.open('w') as stream:
        try:
            child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=env)
            next_storage=start
            while child.poll() is None:
                peak=max(peak,anon(child.pid)+anon(os.getpid()))
                require(peak<ANON_LIMIT,'CPU capture and harness anonymous memory exceeds 8 GB')
                require(time.monotonic()-start<7200,'CPU capture exceeds two-hour bound')
                if time.monotonic()>=next_storage:admission(0);next_storage=time.monotonic()+5
                time.sleep(.5)
            require(child.returncode==0,'CPU draft capture failed: '+str(child.returncode))
        except BaseException as error:
            if child is not None and child.poll() is None:
                child.send_signal(signal.SIGTERM)
                try:child.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=10) # Verified CPU-only process, exact captured PID.
            save(P/f'draft-{compiler}-c{context}-failure.json',dict(passed=False,device_executed=False,error=str(error),output=str(output),log=str(log),peak_anonymous_bytes=peak))
            raise
    native=json.loads((output/'receipt.json').read_text())
    require(native.get('passed') is True and native.get('device_executed') is False,'CPU draft native receipt failed')
    hashes=fixtures(output);require(hashes and any(n.startswith('draft-final-state/') for n in hashes),'missing final draft fixtures')
    receipt=dict(passed=True,device_executed=False,compiler=compiler,context=context,
        binary_sha256=sha(binary),dispatch_sha256=sha(dispatch),output=str(output),table_sha256=sha(table),
        fixture_sha256=hashes,fixture_files=len(hashes),seconds=time.monotonic()-start,
        peak_anonymous_bytes=peak,argv=command,cpu_affinity=sorted(os.sched_getaffinity(0)))
    receipt['log']=compress_log(log)
    save(P/f'draft-{compiler}-c{context}.json',receipt)
    if compiler=='gnu-host':save(P/f'capture-run-{NAME}-c{context}.json',receipt)
    return output,receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--run',action='store_true',help='execute six sequential CPU-only arms after builds complete')
    args=parser.parse_args();require(args.prepare_only != args.run,'choose exactly --prepare-only or --run')
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'invoke through nice -n 19 ionice -c 3')
    B.mkdir(exist_ok=True)
    with (B/'cpu-mtp.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        table,input_receipt=prepare()
        if args.prepare_only:return
        from draft_baseline import load as load_baseline, ORACLE
        baseline=load_baseline();baseline_hash=sha(ORACLE)
        require(input_receipt['source_capture_receipt_sha256']==baseline['source_receipts']['capture-input-'+NAME+'.json']['sha256'],'draft golden/input source differs')
        rows=[];reference_rows=baseline['valid_fixture_sha256'];sealed={}
        for context in CONTEXTS:
            reference,gnu=run_arm('gnu-host',context,table)
            current_rows={k:v for k,v in gnu['fixture_sha256'].items() if k.startswith('row-')}
            require(current_rows==reference_rows,'valid-position draft bytes differ from frozen packet38 oracle')
            scratch,icpx=run_arm('icpx-host',context,table)
            require(icpx['fixture_sha256']==gnu['fixture_sha256'],'GNU/icpx draft fixture bytes differ')
            require({k:v for k,v in icpx['fixture_sha256'].items() if k.startswith('row-')}==reference_rows,'icpx draft bytes differ from frozen packet38 oracle')
            sealed[str(context)]=gnu['fixture_sha256']
            row=dict(context=context,compilers=['gnu-host','icpx-host'],fixture_matches=len(sealed[str(context)]),
                     capacity_prefix_fixture_matches=len(current_rows),baseline_fixture_matches=len(current_rows),baseline_oracle_sha256=baseline_hash,gnu_binary_sha256=gnu['binary_sha256'],
                     icpx_binary_sha256=icpx['binary_sha256'],passed=True)
            save(P/f'draft-capacity-c{context}-comparison.json',row)
            # GNU's exact fixtures remain the coordinator reference. A verified
            # archive keeps icpx logs/JSON and every raw fixture hash, then deletes
            # its duplicate scratch immediately after the comparison receipt.
            row['icpx_archive']=discard(scratch);save(P/f'draft-capacity-c{context}-comparison.json',row);rows.append(row)
        receipt=dict(passed=True,device_executed=False,arms=6,contexts=list(CONTEXTS),
            generated_prefix_tokens=RETAINED_TOKENS,capture_rows=input_receipt['capture_rows'],
            baseline_oracle_sha256=baseline_hash,baseline_compared_arms=6,baseline_fixture_files_per_arm=len(reference_rows),
            rows=rows,draft_capture_fixture_sha256_by_context=sealed,
            draft_capture_input_sha256={NAME:sha(P/('capture-input-'+NAME+'.json'))},
            retained_reference_bytes=sum(build_size(B/f'draft-reference-c{c}') for c in CONTEXTS))
        require(receipt['retained_reference_bytes']<300_000_000,'retained CPU references exceed 300 MB budget')
        save(P/'capacity-draft-gates.json',receipt)
        print(json.dumps(dict(passed=True,arms=6,retained_reference_bytes=receipt['retained_reference_bytes'])),flush=True)


if __name__=='__main__':main()
