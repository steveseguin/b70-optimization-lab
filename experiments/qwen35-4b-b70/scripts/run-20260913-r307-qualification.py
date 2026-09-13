#!/usr/bin/env python3
"""Isolated R307 qualification: token-ID boundary repeats, then fresh 9B strict pairs."""
import argparse, datetime, fcntl, hashlib, json, os, pathlib, re, subprocess, sys, time, urllib.request

REPO = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_IMAGE = 'sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
BENIGN = 'Xe device coredump has been deleted.'
p = argparse.ArgumentParser(); p.add_argument('--out', required=True); p.add_argument('--concurrency', default='1,4'); p.add_argument('--max-num-seqs', type=int, default=4)
p.add_argument('--image', default=DEFAULT_IMAGE, help='Immutable local image ID: sha256 plus 64 lowercase hex digits')
p.add_argument('--candidate', default='r307', help='Safe lowercase candidate label for evidence and container names')
p.add_argument('--inventory', type=pathlib.Path, help='Candidate sha256sum runtime inventory; required for a nondefault image')
a=p.parse_args()
if not re.fullmatch(r'sha256:[0-9a-f]{64}', a.image): p.error('--image must be a full immutable sha256 image ID')
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', a.candidate): p.error('--candidate must be 1-40 lowercase letters, digits or hyphens, starting with a letter or digit')
if a.image != DEFAULT_IMAGE and a.inventory is None: p.error('--inventory is required for a nondefault image')
IMAGE=a.image
inventory=(a.inventory or REPO/'experiments/qwen38-27b-b70/docker/rebase-v0290/r307-contract-digests.sha256').resolve()
if not inventory.is_file(): p.error('--inventory must name an existing file')
inventory_text=inventory.read_text()
inventory_rows=inventory_text.splitlines()
if len(inventory_rows) != 17 or any(not re.fullmatch(r'[0-9a-f]{64}  /opt/venv/lib/python3\.12/site-packages/[^\s]+', row) for row in inventory_rows): p.error('--inventory must contain the complete 17-file sha256sum contract')

if not 1 <= min(map(int,a.concurrency.split(','))) <= max(map(int,a.concurrency.split(','))) <= a.max_num_seqs: p.error('concurrency must fit max-num-seqs')
root=pathlib.Path(a.out).resolve(); root.mkdir(parents=True,exist_ok=True)
lock=open('/tmp/r307-qualification.lock','w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
if (root/'campaign-start.json').exists(): raise SystemExit('Refusing reused campaign root')
start=datetime.datetime.now().astimezone().isoformat(); name=None; proc=None; server_log=None

def log(msg):
    line=f'[{datetime.datetime.now().astimezone().isoformat()}] {msg}'
    print(line,flush=True)
    with (root/'campaign.log').open('a') as f: f.write(line+'\n')

def cmd(args, output=None, env=None, timeout=240):
    if output:
        with pathlib.Path(output).open('w') as f: return subprocess.run(args,cwd=REPO,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout,check=True)
    return subprocess.run(args,cwd=REPO,env=env,capture_output=True,text=True,timeout=timeout,check=True).stdout

def journal(label):
    data=cmd(['journalctl','-k','--since',start,'--no-pager'])
    (root/f'{label}-journal.txt').write_text(data)
    bad=[s for s in data.splitlines() if FAULT.search(s) and BENIGN not in s]
    if bad: raise RuntimeError('New kernel fault: '+ '\n'.join(bad))

def health(label):
    journal(label+'-before')
    cmd(['xpu-smi','discovery'],root/f'{label}-discovery.txt')
    if (root/f'{label}-discovery.txt').read_text().count('Device State: normal') != 2: raise RuntimeError('Expected two normal B70 devices')
    cmd(['bash',str(REPO/'scripts/check-qwen36-xpu-xccl-health.sh')],root/f'{label}-compute-xccl.txt',timeout=180)
    journal(label+'-after')

def stop():
    global name,proc,server_log
    if name:
        try:
            inspect=cmd(['docker','inspect',name]); (root/f'{name}-inspect.json').write_text(inspect)
        except subprocess.CalledProcessError: pass
        subprocess.run(['docker','stop','-t','60',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=80)
        if proc:
            try: proc.wait(timeout=30)
            except subprocess.TimeoutExpired: proc.terminate(); proc.wait(timeout=15)
        # These launchers use --rm; only remove this campaign's named container if it remains.
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
        name=None; proc=None
        if server_log: server_log.close(); server_log=None

def launch(model, depth, label):
    global name,proc,server_log
    if cmd(['docker','ps','-q']).strip(): raise RuntimeError('Another container is running')
    health(label+'-preflight')
    d=root/label; d.mkdir(); name=a.candidate+'-qual-'+label
    env=os.environ.copy(); env.update(IMAGE=IMAGE,EXPECTED_IMAGE_ID=IMAGE,SKIP_IMAGE_CONTRACT='0',EXPECTED_KERNEL_HEAD='6d92b1bfbf32767ecda8e819613eb151e70030ad',MODEL_DIR=f'/home/steve/llm-models/qwen35-{model}-w4a16',CONTAINER_NAME=name,SERVED_MODEL_NAME='m',PORT='18186',VLLM_CACHE_DIR=str(d/'cache'),MTP_DEPTH=str(depth),TENSOR_PARALLEL_SIZE='1',XPU_DEVICE_MASK='0',MAX_MODEL_LEN='256',MAX_NUM_SEQS=str(a.max_num_seqs),MAX_NUM_BATCHED_TOKENS='1024',VLLM_USE_V2_MODEL_RUNNER='0')
    (d/'launch-env.json').write_text(json.dumps({k:env[k] for k in ['IMAGE','EXPECTED_IMAGE_ID','SKIP_IMAGE_CONTRACT','MODEL_DIR','CONTAINER_NAME','VLLM_CACHE_DIR','MTP_DEPTH','MAX_MODEL_LEN','MAX_NUM_SEQS','XPU_DEVICE_MASK']},indent=2)+'\n')
    launcher=REPO/f'repro/qwen35-{model}-w4a16-b70/scripts/run-qwen35-{model}-w4a16-server.sh'
    server_log=(d/'server.log').open('w'); proc=subprocess.Popen(['bash',str(launcher)],cwd=REPO,env=env,stdout=server_log,stderr=subprocess.STDOUT)
    log(f'{label}: launching immutable {a.candidate} image')
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        journal(label+'-startup')
        if proc.poll() is not None: raise RuntimeError(f'{label}: launcher exited {proc.returncode}')
        try:
            with urllib.request.urlopen('http://127.0.0.1:18186/health',timeout=3) as r:
                if r.status==200: log(f'{label}: healthy'); return d
        except Exception: pass
        time.sleep(5)
    raise RuntimeError(f'{label}: health timeout')

(root/'campaign-start.json').write_text(json.dumps({'started':start,'image':IMAGE,'candidate':a.candidate,'inventory_path':str(inventory),'inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest(),'repo_head':cmd(['git','rev-parse','HEAD']).strip(),'scope':f'TP1 fixed depth 3; boundary concurrency={a.concurrency}; max_num_seqs={a.max_num_seqs}; strict 9B','runner_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256((REPO/'experiments/qwen35-4b-b70/probes/boundary-token-id-probe.py').read_bytes()).hexdigest()},indent=2)+'\n')
try:
    if cmd(['docker','ps','-q']).strip(): raise RuntimeError('Host already busy')
    cmd(['docker','image','inspect',IMAGE],root/'image-inspect.json')
    inspected=json.loads((root/'image-inspect.json').read_text())
    if len(inspected) != 1 or inspected[0]['Id'] != IMAGE: raise RuntimeError('Immutable image ID mismatch')
    (root/'candidate-contract.sha256').write_text(inventory_text)
    observed=cmd(['docker','run','--rm','-w','/','--entrypoint','sha256sum',IMAGE,*[row.split()[1] for row in inventory_rows]])
    (root/'candidate-observed.sha256').write_text(observed)
    if observed != inventory_text: raise RuntimeError('Candidate runtime inventory mismatch')
    contract_env=os.environ.copy(); contract_env['SKIP_IMAGE_CONTRACT']='0'
    cmd(['bash',str(REPO/'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh'),'mtp1-serial-fa-split-gdn',IMAGE],root/'candidate-image-contract.log',contract_env)
    for model in ['4b','9b']:
        oracle=None
        for arm,depth in [('oracle',0),('mtp3-a',3),('mtp3-b',3)]:
            label=f'{model}-{arm}'; d=launch(model,depth,label)
            probe=['python3',str(REPO/'experiments/qwen35-4b-b70/probes/boundary-token-id-probe.py'),'--base','http://127.0.0.1:18186','--model','m','--concurrency',a.concurrency,'--mode','compare' if oracle else 'oracle','--identity',f'{IMAGE}; model={model}; depth={depth}; TP1; cache-off','--out',str(d/'result.json')]
            if oracle: probe+=['--oracle',str(oracle)]
            cmd(probe,d/'probe.log',timeout=1800)
            if oracle is None: oracle=d/'result.json'
            log(f'{label}: token-ID probe passed')
            stop(); health(label+'-postflight')
    log('9B strict pairs: starting')
    env=os.environ.copy(); env.update(IMAGE=IMAGE,IMAGE_ID=IMAGE,RUN=a.candidate+'-qualified',ROOT=str(root/'9b-strict'),LANE='qwen35-9b-w4a16',MODEL_DIR='/home/steve/llm-models/qwen35-9b-w4a16',MODEL_MANIFEST=str(REPO/'repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json'),QUANT='compressed-tensors',DRAFT_HEAD='1',W4A16_PAD='0',GRAPH='1',TP='1',DEPTH='3',STAGES='strict',LOAD_MEMORY_MIB='11500',SKIP_IMAGE_CONTRACT='0',EXPECTED_KERNEL_HEAD='6d92b1bfbf32767ecda8e819613eb151e70030ad',VLLM_USE_V2_MODEL_RUNNER='0',VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST='/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt',VLLM_XPU_FP16_LINEAR_CLASSPAD='0')
    cmd(['timeout','--signal=TERM','--kill-after=120s','3600','bash',str(REPO/'experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh')],root/'9b-strict-wrapper.log',env,timeout=3900)
    health('final')
    (root/'DONE').write_text('All requested qualification stages passed\n'); log('Qualification complete')
except BaseException as exc:
    log(f'FAILED: {exc}'); (root/'FAILED').write_text(str(exc)+'\n')
    try: stop(); health('failure-postflight')
    except Exception as cleanup: log(f'Cleanup/postflight failure: {cleanup}')
    raise
finally:
    stop()
