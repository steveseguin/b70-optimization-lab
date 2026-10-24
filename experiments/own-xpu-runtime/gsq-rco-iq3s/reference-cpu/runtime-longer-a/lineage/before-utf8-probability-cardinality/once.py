#!/usr/bin/env python3
"""One root-admitted CPU reference owner, three fixed requests. No retries or hard kill."""
import argparse, hashlib, math, http.client, json, os, pathlib, re, resource, shutil, signal, socket, subprocess, threading, time
HERE=pathlib.Path(__file__).resolve().parent
REF=HERE.parent
ROOT=pathlib.Path('/home/steve/llm-optimizations')
LANE=REF.parent
RUN=pathlib.Path('/mnt/usb-models/own-xpu-runtime-reference/sc117-cpu-23b0202a-b/runtime-longer-a')
PORT=18088
GIB=1<<30
QUOTA=128<<20
ROOT_FLOOR=27_000_000_000+(64<<20)
RAM_INITIAL=101_032_431_104
ADMISSION=REF/'runtime-a/evidence/offline-runtime-admission.json'
BUILD=REF/'build-b/evidence/build-result.json'
CENSUS=LANE/'metadata/new-census.json'
REQUEST=HERE/'requests.json'
CUSTOM=LANE/'recurrent-f32/operating/launch-b/evidence/device-b/review.json'
CUSTOM_SHA='08b09b122647c553c4d71c2050cdca6f5f223c613fc88af4a8046ebeddb4e1c3'

def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def load(p): return json.loads(pathlib.Path(p).read_text())
def save(p,obj):
    with open(p,'x') as f:
        json.dump(obj,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def memory():
    return int(re.search(r'^MemAvailable:\s+(\d+)',pathlib.Path('/proc/meminfo').read_text(),re.M)[1])*1024
def identity(p):
    s=p.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def clean_env():
    return {'PATH':'/usr/bin:/bin','HOME':os.environ['HOME'],'TMPDIR':str(RUN/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','OMP_NUM_THREADS':'2','OMP_THREAD_LIMIT':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','NO_PROXY':'127.0.0.1,localhost'}
def scan(binary):
    require(not list(binary.parent.glob('libggml*.so*')),'neighbor backend module')
    cache=(binary.parent.parent/'CMakeCache.txt').read_text()
    require('GGML_BACKEND_DIR:PATH=\n' in cache,'nonempty compiled backend search path')
    require('GGML_BACKEND_DL:BOOL=OFF' in cache,'backend dynamic build changed')
    for name in ['cwd','tmp']:
        p=RUN/name
        if p.exists(): require(not any(p.iterdir()),'nonempty isolated '+name)
def model_stats(census):
    for row in census['shards']:
        p=pathlib.Path(row['path']); require(not p.is_symlink(),'model symlink')
        require(identity(p)==row['stat_identity'],'model identity drift')
def build_plan():
    a=load(ADMISSION); b=load(BUILD);c=load(CENSUS);r=load(REQUEST)
    require(a['passed'] and b['passed'] and not a['binary_invoked'],'offline admission')
    binary=pathlib.Path(a['binary']);require(str(binary)==b['binary'],'binary path')
    require(sha(binary)==a['binary_sha256']==b['binary_sha256'],'binary hash')
    require(sha(a['offline_review_path'])==a['offline_review_sha256'],'offline review drift')
    require(load(a['offline_review_path'])['build_receipt_sha256']==sha(BUILD),'build receipt drift')
    for lib in a['libraries']:
        require(str(pathlib.Path(lib['path']).resolve())==lib['resolved'] and sha(lib['resolved'])==lib['sha256'],'library drift')
    require(sha(r['manifest_path'])==r['manifest_sha256'],'original prompt manifest');manifest=load(r['manifest_path'])
    require(len(r['cases'])==3,'three fixed requests')
    template=load(REF/'request-proposal.json')
    for i,case in enumerate(r['cases']):
        expected=dict(template,prompt=manifest['prompts'][i]['tokens'],n_predict=512,temperature=0)
        require(case==dict(index=i,id=manifest['prompts'][i]['prompt_id'],request=expected),'exact original numeric request/cap/sampler')
    review=load(HERE/'evidence/independent-review.json');require(review['passed'],'independent runtime source review')
    for name,want in review['source_sha256'].items():require(sha(name)==want,'reviewed source drift')
    require(sha(CUSTOM)==CUSTOM_SHA and load(CUSTOM)['passed'],'custom comparison authority')
    model_stats(c);scan(binary)
    argv=[str(binary),'-m',c['shards'][0]['path'],'--device','none','--n-gpu-layers','0','--host','127.0.0.1','--port',str(PORT),'--ctx-size','4096','--parallel','1','--threads','2','--threads-batch','2','--threads-http','1','--cache-type-k','bf16','--cache-type-v','bf16','--flash-attn','off','--no-warmup','--cache-ram','0','--no-cache-prompt','--cache-reuse','0','--no-context-shift','--predict','512','--log-verbosity','4']
    return {'schema':'gsq.reference.cpu.runtime-longer-a.v1','argv':argv,'environment':clean_env(),'cwd':str(RUN/'cwd'),'output':str(RUN),'binary_sha256':a['binary_sha256'],'source_sha256':{str(p):sha(p) for p in [pathlib.Path(__file__),ADMISSION,BUILD,CENSUS,REQUEST,CUSTOM,REF/'request-proposal.json',HERE/'evidence/independent-review.json']},'requests':r['cases'],'deadline_seconds':3600,'ram_initial':RAM_INITIAL,'ram_floor':8*GIB,'address_space':128*GIB,'output_quota':QUOTA,'usb_floor':2*GIB,'root_floor':ROOT_FLOOR,'model_header_validation_at_run':True,'no_reference_quality_claim':True}
def limits():
    os.nice(19);os.sched_setaffinity(0,set(range(8,16))|set(range(24,32)))
    resource.setrlimit(resource.RLIMIT_AS,(128*GIB,128*GIB));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def socket_owned(pid):
    inodes=set()
    for p in pathlib.Path('/proc',str(pid),'fd').iterdir():
        try: target=os.readlink(p)
        except FileNotFoundError: continue
        if target.startswith('socket:['): inodes.add(target[8:-1])
    for line in pathlib.Path('/proc/net/tcp').read_text().splitlines()[1:]:
        cols=line.split()
        if cols[1]==f'0100007F:{PORT:04X}' and cols[3]=='0A': return cols[9] in inodes
    return False
def no_device(pid,allowed):
    for p in pathlib.Path('/proc',str(pid),'fd').iterdir():
        try: target=os.readlink(p)
        except FileNotFoundError: continue
        require(not target.startswith(('/dev/dri/','/dev/kfd','/dev/nvidia','/dev/accel/')),'unexpected accelerator FD')
    for line in pathlib.Path('/proc',str(pid),'maps').read_text().splitlines():
        parts=line.split(maxsplit=5)
        if len(parts)==6 and parts[5].startswith('/') and '.so' in pathlib.Path(parts[5]).name:
            require(str(pathlib.Path(parts[5]).resolve()) in allowed,'unexpected loaded shared library '+parts[5])
def request_http(method,path,body=None,timeout=2):
    conn=http.client.HTTPConnection('127.0.0.1',PORT,timeout=timeout)
    try:
        conn.request(method,path,body=None if body is None else json.dumps(body),headers={'Content-Type':'application/json'})
        response=conn.getresponse();raw=response.read((8<<20)+1)
        require(len(raw)<=8<<20,'HTTP response exceeds bound')
        return response.status,json.loads(raw)
    finally: conn.close()
def dtype_log(text):
    require(re.search(r'K \(bf16\).*V \(bf16\)',text),'actual BF16 K/V log missing')
    require(re.search(r'R \(f32\).*S \(f32\).*P \(f32\)',text),'actual F32 recurrent R/S/P log missing')
def response_check(r,request):
    count=len(request['prompt']);tokens=r['tokens']
    require(r['tokens_evaluated']==count and r['timings']['prompt_n']==count and r['timings']['cache_n']==0 and not r['truncated'],'full uncached numeric prompt')
    require(isinstance(tokens,list) and 0<len(tokens)<=512 and all(type(t)==int for t in tokens),'returned tokens')
    require(r['stop'] and r['stop_type'] in ['eos','limit'] and (r['stop_type']!='limit' or len(tokens)==512),'natural EOS/full cap')
    require(r['tokens_predicted']==len(tokens),'actual prediction count')
    g=r['generation_settings']
    require(g['temperature']==0 and g['samplers']==['temperature'] and g['n_predict']==512 and not g['ignore_eos'] and g['n_probs']==32 and not g['post_sampling_probs'],'effective greedy sampler')
    require(g['repeat_penalty']==1 and g['presence_penalty']==g['frequency_penalty']==0 and g['speculative.types']=='none' and not g['logit_bias'] and not g['grammar'] and not g['lora'],'neutral reference generation')
    probs=r['completion_probabilities'];require(len(probs)==len(tokens),'all output probability rows')
    for token,row in zip(tokens,probs):
        top=row['top_logprobs'];require(row['id']==token and len(top)==32 and len({x['id'] for x in top})==32,'saved chosen/top32 IDs')
        require(all(math.isfinite(x['logprob']) for x in top) and math.isfinite(row['logprob']),'finite retained log probabilities')
        chosen=[x for x in top if x['id']==token];require(len(chosen)==1 and chosen[0]['logprob']==row['logprob']==max(x['logprob'] for x in top),'chosen greedy argmax in retained pre-sampling top32')
    # tokens_cached is end-of-request resident sequence length, not reused-prompt count.
    # Only timings.cache_n above is the request's cached-input count.

def run(plan):
    require(not RUN.exists(),'fresh runtime output required')
    require(memory()>=RAM_INITIAL,'initial memory floor')
    require(shutil.disk_usage(ROOT).free>=ROOT_FLOOR,'root floor')
    require(shutil.disk_usage(RUN.parent).free>=2*GIB+QUOTA,'USB initial floor/quota')
    require(RUN.parent.stat().st_dev==load(CENSUS)['shards'][0]['stat_identity'][0],'external filesystem identity')
    with socket.socket() as probe: probe.bind(('127.0.0.1',PORT))
    RUN.mkdir(mode=0o700)
    for name in ['cwd','tmp']: (RUN/name).mkdir(mode=0o700)
    save(RUN/'plan.json',plan);save(RUN/'requests.json',plan['requests'])
    # Header-only authentication before loading. No header read in --plan mode.
    c=load(CENSUS)
    for row in c['shards']:
        with open(row['path'],'rb',opener=lambda p,f:os.open(p,f|os.O_NOFOLLOW)) as f:
            s=os.fstat(f.fileno());stamp=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
            require(stamp==row['stat_identity'],'held model identity')
            require(hashlib.sha256(f.read(row['header_bytes_read'])).hexdigest()==row['header_sha256'],'model header hash')
            require(identity(pathlib.Path(row['path']))==stamp,'model path changed')
    a=load(ADMISSION);allowed={x['resolved'] for x in a['libraries']}
    start=time.monotonic();p=None;failure=None;responded=False;sent=False;stats=[];completed=[]
    def monitor():
        require(p.poll() is None,'reference exited before completion')
        require(time.monotonic()-start<3600,'total runtime deadline')
        require(memory()>=8*GIB,'runtime memory floor')
        require(shutil.disk_usage(ROOT).free>=ROOT_FLOOR,'runtime root floor')
        require(shutil.disk_usage(RUN).free>=2*GIB,'runtime USB floor')
        require(sum(x.stat().st_size for x in RUN.rglob('*') if x.is_file())<=QUOTA,'runtime output quota')
        no_device(p.pid,allowed)
        stats.append({'elapsed':time.monotonic()-start,'mem_available':memory(),'status':pathlib.Path('/proc',str(p.pid),'status').read_text()})
    try:
        with open(RUN/'server.log','xb',buffering=0) as log:
            p=subprocess.Popen(plan['argv'],cwd=plan['cwd'],env=plan['environment'],stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits,start_new_session=True)
            save(RUN/'owner.json',{'pid':p.pid,'start_ticks':pathlib.Path('/proc',str(p.pid),'stat').read_text().rsplit(')',1)[1].split()[19]})
            while True:
                monitor()
                if socket_owned(p.pid):
                    try: status,h=request_http('GET','/health')
                    except (OSError,ValueError,http.client.HTTPException): status=0
                    if status==200: break
                time.sleep(2)
            dtype_log((RUN/'server.log').read_text())
            for case in plan['requests']:
                monitor();require(socket_owned(p.pid),'listener changed before request')
                answer={};done=threading.Event();request=case['request'];prefix=f"request-{case['index']:02d}"
                save(RUN/(prefix+'.json'),case)
                def request_once():
                    try: answer['status'],answer['response']=request_http('POST','/completion',request,3600)
                    except BaseException as e: answer['error']=repr(e)
                    finally: done.set()
                threading.Thread(target=request_once,daemon=True).start()
                while not done.wait(2): monitor()
                monitor();save(RUN/(prefix+'-response.json'),answer)
                require(answer.get('status')==200,'completion failed '+str(answer.get('error')))
                response_check(answer['response'],request)
                completed.append(dict(index=case['index'],id=case['id'],response_sha256=sha(RUN/(prefix+'-response.json')),tokens=answer['response']['tokens'],stop_type=answer['response']['stop_type']))
                save(RUN/(prefix+'-validation.json'),dict(passed=True,request_sha256=sha(RUN/(prefix+'.json')),**completed[-1]))
            save(RUN/'reference-results.json',dict(passed=True,cases=completed,scope='Three fixed CPU references; native target comparison is a separate closed run'))
            responded=True
    except BaseException as e: failure=repr(e)
    finally:
        if p is not None and p.poll() is None:
            signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN)
            try: p.send_signal(signal.SIGTERM);sent=True
            except ProcessLookupError: p.poll()
            # Retain owner indefinitely if cooperative close cannot complete; never retry/kill.
            while p.poll() is None: time.sleep(2)
        try: model_stats(c)
        except BaseException as e:
            if failure is None: failure=repr(e)
        save(RUN/'monitor.json',stats)
        save(RUN/'terminal.json',{'passed':failure is None and responded and p is not None and p.returncode==0,'first_error':failure,'response_valid':responded,'completed_requests':len(completed),'signal_sent_once':sent,'returncode':None if p is None else p.returncode,'owner_exited':p is not None and p.poll() is not None,'elapsed_seconds':time.monotonic()-start,'scope':'One CPU reference owner, three original prompts; no speed or general-quality qualification','plan_sha256':sha(RUN/'plan.json')})
    return 0 if failure is None and responded and p is not None and p.returncode==0 else 1
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--plan-sha256');args=ap.parse_args();plan=build_plan()
    if args.run:
        require(args.plan_sha256==hashlib.sha256((json.dumps(plan,indent=2)+'\n').encode()).hexdigest(),'explicit admitted plan hash required')
        def stop(signum,frame): raise RuntimeError('coordinator stop signal '+str(signum))
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        try: code=run(plan)
        except BaseException as e:
            if RUN.exists() and not (RUN/'terminal.json').exists():
                save(RUN/'startup-failure.json',{'passed':False,'error':repr(e),'scope':'Failure before terminal receipt; inspect retained owner/plan and never infer clean closure'})
            raise
        raise SystemExit(code)
    print(json.dumps(plan,indent=2))
