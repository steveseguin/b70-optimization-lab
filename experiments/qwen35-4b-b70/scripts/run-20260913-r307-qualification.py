#!/usr/bin/env python3
"""Isolated R307 qualification: token-ID boundary repeats, then fresh 9B strict pairs."""
import argparse, datetime, fcntl, json, os, pathlib, re, subprocess, sys, time, urllib.request

REPO = pathlib.Path(__file__).resolve().parents[3]
IMAGE = 'sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3'
FAULT = re.compile(r'(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup', re.I)
BENIGN = 'Xe device coredump has been deleted.'
p = argparse.ArgumentParser(); p.add_argument('--out', required=True); a=p.parse_args()
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
    d=root/label; d.mkdir(); name='r307-qual-'+label
    env=os.environ.copy(); env.update(IMAGE=IMAGE,EXPECTED_IMAGE_ID=IMAGE,SKIP_IMAGE_CONTRACT='0',EXPECTED_KERNEL_HEAD='6d92b1bfbf32767ecda8e819613eb151e70030ad',MODEL_DIR=f'/home/steve/llm-models/qwen35-{model}-w4a16',CONTAINER_NAME=name,SERVED_MODEL_NAME='m',PORT='18186',VLLM_CACHE_DIR=str(d/'cache'),MTP_DEPTH=str(depth),TENSOR_PARALLEL_SIZE='1',XPU_DEVICE_MASK='0',MAX_MODEL_LEN='256',MAX_NUM_SEQS='4',MAX_NUM_BATCHED_TOKENS='1024',VLLM_USE_V2_MODEL_RUNNER='0')
    (d/'launch-env.json').write_text(json.dumps({k:env[k] for k in ['IMAGE','EXPECTED_IMAGE_ID','SKIP_IMAGE_CONTRACT','MODEL_DIR','CONTAINER_NAME','VLLM_CACHE_DIR','MTP_DEPTH','MAX_MODEL_LEN','MAX_NUM_SEQS','XPU_DEVICE_MASK']},indent=2)+'\n')
    launcher=REPO/f'repro/qwen35-{model}-w4a16-b70/scripts/run-qwen35-{model}-w4a16-server.sh'
    server_log=(d/'server.log').open('w'); proc=subprocess.Popen(['bash',str(launcher)],cwd=REPO,env=env,stdout=server_log,stderr=subprocess.STDOUT)
    log(f'{label}: launching immutable R307 image')
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

(root/'campaign-start.json').write_text(json.dumps({'started':start,'image':IMAGE,'repo_head':cmd(['git','rev-parse','HEAD']).strip(),'scope':'TP1 fixed depth 3; boundary c1/c4; strict 9B'},indent=2)+'\n')
try:
    if cmd(['docker','ps','-q']).strip(): raise RuntimeError('Host already busy')
    cmd(['docker','image','inspect',IMAGE],root/'image-inspect.json')
    for model in ['4b','9b']:
        oracle=None
        for arm,depth in [('oracle',0),('mtp3-a',3),('mtp3-b',3)]:
            label=f'{model}-{arm}'; d=launch(model,depth,label)
            probe=['python3',str(REPO/'experiments/qwen35-4b-b70/probes/boundary-token-id-probe.py'),'--base','http://127.0.0.1:18186','--model','m','--mode','compare' if oracle else 'oracle','--identity',f'{IMAGE}; model={model}; depth={depth}; TP1; cache-off','--out',str(d/'result.json')]
            if oracle: probe+=['--oracle',str(oracle)]
            cmd(probe,d/'probe.log',timeout=1800)
            if oracle is None: oracle=d/'result.json'
            log(f'{label}: token-ID probe passed')
            stop(); health(label+'-postflight')
    log('9B strict pairs: starting')
    env=os.environ.copy(); env.update(IMAGE=IMAGE,IMAGE_ID=IMAGE,RUN='r307-qualified',ROOT=str(root/'9b-strict'),LANE='qwen35-9b-w4a16',MODEL_DIR='/home/steve/llm-models/qwen35-9b-w4a16',MODEL_MANIFEST=str(REPO/'repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json'),QUANT='compressed-tensors',DRAFT_HEAD='1',W4A16_PAD='0',GRAPH='1',TP='1',DEPTH='3',STAGES='strict',LOAD_MEMORY_MIB='11500',SKIP_IMAGE_CONTRACT='0',EXPECTED_KERNEL_HEAD='6d92b1bfbf32767ecda8e819613eb151e70030ad',VLLM_USE_V2_MODEL_RUNNER='0',VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST='/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt',VLLM_XPU_FP16_LINEAR_CLASSPAD='0')
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
