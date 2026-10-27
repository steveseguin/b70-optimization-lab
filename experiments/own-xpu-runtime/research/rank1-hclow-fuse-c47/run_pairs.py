#!/usr/bin/env python3
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

LAB=Path('/dev/shm/ownrt-lab-r1-c47hclow')
OUT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/rank1-hclow-fuse-c47')
DRIVER=LAB/'tp_rank1_driver.py'
LOCK='/dev/shm/card47hclow.lock'
FAULT=re.compile(r'Fault response|CAT error|engine reset|GPU HANG|wedged|Timedout|timed-out job',re.I)
def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def kernel_lines(start):
    p=subprocess.run(['journalctl','-k','--since',f'@{start}','--no-pager'],capture_output=True,text=True)
    return '\n'.join(x for x in p.stdout.splitlines() if FAULT.search(x))

def available_gib():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'): return int(line.split()[1])/1048576
    raise RuntimeError('MemAvailable missing')

def run(name,arm):
    out=LAB/'runs'/name
    launch=json.loads((LAB/'launch-ref.json').read_text())
    launch['environment'].pop('LD_PRELOAD',None)
    launch['environment'].pop('ONEAPI_DEVICE_SELECTOR',None)
    launch['environment']['OWNRT_DECODE_PROFILE']='0'
    if arm=='candidate':
        launch['argv'][3]=str(LAB/'build-candidate/sc117-engine')
        launch['environment']['OWNRT_HCLOW_FUSE']='1'
    else:
        launch['argv'][3]='/dev/shm/engine-build-svc-b19-gdnprep-20261026/sc117-engine'
        launch['environment'].pop('OWNRT_HCLOW_FUSE',None)
    actual=LAB/'runs'/f'launch-{name}.json';actual.parent.mkdir(exist_ok=True)
    actual.write_text(json.dumps(launch,indent=1)+'\n')
    avail=available_gib()
    if avail<35: raise RuntimeError(f'MemAvailable {avail:.2f} GiB below 35 GiB admission')
    env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('ONEAPI_DEVICE_SELECTOR',None)
    cmd=['flock',LOCK,'nice','-n','10','taskset','-c','8-15,24-31','python3','-B',str(DRIVER),'run','--launch',str(actual),'--out',str(out),'--steps','48','--prompt','300','--batched','--rows','32','--cache',str(LAB/'cache')]
    start=int(time.time())
    with (LAB/'runs'/f'{name}.out').open('w') as log:
        rc=subprocess.run(cmd,cwd=LAB,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    faults=kernel_lines(start)
    (OUT/f'kernel-{name}.log').write_text(faults+('\n' if faults else ''))
    if faults:
        (LAB/'HALT').write_text(faults+'\n')
        raise RuntimeError(f'kernel fault after {name}; no retry')
    if rc: raise RuntimeError(f'{name} driver rc={rc}; see {out}/rank1.log')
    summary=json.loads((out/'summary.json').read_text())
    if summary['rc'] or summary['steps']!=48: raise RuntimeError(f'{name} bad summary')
    fusion=out/'rank1/decode-fusion.json'
    if arm=='candidate':
        f=json.loads(fusion.read_text())
        if f.get('low_act')!=50: raise RuntimeError(f'{name} expected 50 fused low sites, got {f}')
    med=sorted(summary['half_ms'])[len(summary['half_ms'])//2]
    print(f'{name} arm={arm} median_half_ms={med:.6f} prompt_ms={summary["prompt_ms"]:.1f} load_s={summary["load_s"]:.1f} MemAvailable={avail:.1f}GiB',flush=True)
    return summary

def compare(pair,left,right):
    a=LAB/'runs'/left;b=LAB/'runs'/right
    p=subprocess.run(['python3','-B',str(DRIVER),'compare',str(a),str(b)],capture_output=True,text=True)
    if p.returncode: raise RuntimeError(f'{pair} state mismatch: {p.stdout}')
    result=json.loads(p.stdout)
    if result['compared']!=1079 or result['differ_count'] or result['only_one_side'] or result['other_fields_differ']:
        raise RuntimeError(f'{pair} incomplete state comparison: {result}')
    sa=json.loads((a/'summary.json').read_text());sb=json.loads((b/'summary.json').read_text())
    if sa['tokens']!=sb['tokens']: raise RuntimeError(f'{pair} token mismatch')
    result['tokens_equal']=True
    (OUT/f'compare-{pair}.json').write_text(json.dumps(result)+'\n')
    return result

def main():
    if (LAB/'HALT').exists(): raise RuntimeError('HALT present; no launches')
    (LAB/'runs').mkdir(exist_ok=True)
    preexisting=kernel_lines(int(time.time())-900)
    if preexisting: raise RuntimeError('recent kernel fault lines; no launches: '+preexisting)
    attempt=os.environ.get('ATTEMPT','')
    pairs=[(attempt+'ab1','reference','candidate'),(attempt+'ba2','candidate','reference'),(attempt+'ab3','reference','candidate')]
    summaries={};comparisons={};deltas=[]
    for pair,first,second in pairs:
        names={}
        for arm in (first,second):
            name=f'{pair}-{arm}';summaries[name]=run(name,arm);names[arm]=name
        comparisons[pair]=compare(pair,names['reference'],names['candidate'])
        med=lambda s:sorted(s['half_ms'])[len(s['half_ms'])//2]
        delta=med(summaries[names['reference']])-med(summaries[names['candidate']]);deltas.append(delta)
        print(f'{pair} paired_reference_minus_candidate_ms={delta:.6f} buffers=1079 tokens_equal=true',flush=True)
    ordered=sorted(deltas);median=ordered[1]
    result={
      'card':'0000:47:00.0','driver':'rank1','profile':0,'pairs':['AB','BA','AB'],'steps_per_run':48,'prompt_rows':300,
      'fused_low_sites_per_candidate':50,'all_tokens_equal':True,'all_target_buffers_exact':True,
      'runs':{k:{'arm':('candidate' if k.endswith('candidate') else 'reference'),'half_ms':v['half_ms'],'median_half_ms':sorted(v['half_ms'])[24],
                 'tokens':v['tokens'],'load_s':v['load_s'],'prompt_ms':v['prompt_ms']} for k,v in summaries.items()},
      'comparisons':comparisons,'paired_reference_minus_candidate_ms':deltas,'median_paired_delta_ms':median,
      'keep_threshold_ms':0.1,'keep':median>=0.1,'kernel_faults':0,'mem_available_minimum_gib':35,
    }
    result['baseline_binary_sha256']=sha256('/dev/shm/engine-build-svc-b19-gdnprep-20261026/sc117-engine')
    result['candidate_binary_sha256']=sha256(LAB/'build-candidate/sc117-engine')
    result['cpu_test']={'output':'cpu-test.out','cases':6,'mismatches':0,'gpu_access':'blocked by nodri.so'}
    result['verdict']='keep' if result['keep'] else 'drop'
    (OUT/'results.json').write_text(json.dumps(result,indent=1)+'\n')
    (OUT/f'results{"-"+attempt if attempt else ""}.json').write_text(json.dumps(result,indent=1)+'\n')
    print(json.dumps({'median_paired_delta_ms':median,'keep':median>=0.1,'exact_comparisons':len(comparisons)}))

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr)
        sys.exit(1)
