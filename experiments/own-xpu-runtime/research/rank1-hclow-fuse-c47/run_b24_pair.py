#!/usr/bin/env python3
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
LAB=Path('/dev/shm/ownrt-lab-r1-c47hclow')
OUT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/rank1-hclow-fuse-c47')
DRIVER=LAB/'tp_rank1_driver.py'
FAULT=re.compile(r'Fault response|CAT error|engine reset|GPU HANG|wedged|Timedout|timed-out job',re.I)
BINARIES={'b19':'/dev/shm/engine-build-svc-b19-gdnprep-20261026/sc117-engine','b24':'/dev/shm/engine-build-svc-b24-gdnprefill-20261027/sc117-engine'}

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def faults(start):
 p=subprocess.run(['journalctl','-k','--since',f'@{start}','--no-pager'],capture_output=True,text=True)
 return '\n'.join(x for x in p.stdout.splitlines() if FAULT.search(x))
def available():
 for line in Path('/proc/meminfo').read_text().splitlines():
  if line.startswith('MemAvailable:'):return int(line.split()[1])/1048576
 raise RuntimeError('MemAvailable unavailable')
def run(arm):
 avail=available()
 if avail<35:raise RuntimeError(f'MemAvailable {avail:.2f} GiB below 35 GiB; no load')
 launch=json.loads((LAB/'launch-ref.json').read_text());launch['argv'][3]=BINARIES[arm]
 launch['argv'][launch['argv'].index('--context')+1]='65536'
 launch['environment']['OWNRT_DECODE_PROFILE']='0';launch['environment'].pop('OWNRT_HCLOW_FUSE',None)
 launch['environment'].pop('LD_PRELOAD',None);launch['environment'].pop('ONEAPI_DEVICE_SELECTOR',None)
 actual=LAB/'runs'/f'launch-{arm}-prompt4096.json';actual.write_text(json.dumps(launch,indent=1)+'\n')
 out=LAB/'runs'/f'{arm}-prompt4096'
 env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('ONEAPI_DEVICE_SELECTOR',None)
 cmd=['flock','/dev/shm/card47hclow.lock','nice','-n','10','taskset','-c','8-15,24-31','python3','-B',str(DRIVER),'run','--launch',str(actual),'--out',str(out),'--steps','48','--prompt','4096','--batched','--rows','256','--cache',str(LAB/'cache')]
 start=int(time.time())
 with (LAB/'runs'/f'{arm}-prompt4096.out').open('w') as log:rc=subprocess.run(cmd,cwd=LAB,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
 lines=faults(start);(OUT/f'kernel-{arm}-prompt4096.log').write_text(lines+('\n' if lines else ''))
 if lines:
  (LAB/'HALT').write_text(lines+'\n');raise RuntimeError(f'kernel fault after {arm}; no retry')
 if rc:raise RuntimeError(f'{arm} driver rc={rc}; see {out}/rank1.log')
 s=json.loads((out/'summary.json').read_text())
 if s['rc'] or s['prompt']!=4096 or s['rows']!=256 or not s['batched']:raise RuntimeError(f'{arm} wrong run identity')
 print(f'{arm} prompt_ms={s["prompt_ms"]:.6f} median_half_ms={sorted(s["half_ms"])[24]:.6f} load_s={s["load_s"]:.1f} MemAvailable={avail:.1f}GiB',flush=True)
 return s,avail

def main():
 if (LAB/'HALT').exists():raise RuntimeError('HALT present; no launch')
 recent=faults(int(time.time())-900)
 if recent:raise RuntimeError('recent kernel fault lines; no launch: '+recent)
 summaries={};admitted={}
 for arm in ('b19','b24'):summaries[arm],admitted[arm]=run(arm)
 a=LAB/'runs/b19-prompt4096';b=LAB/'runs/b24-prompt4096'
 p=subprocess.run(['python3','-B',str(DRIVER),'compare',str(a),str(b)],capture_output=True,text=True)
 if p.returncode:raise RuntimeError('state comparison failed: '+p.stdout)
 comparison=json.loads(p.stdout);comparison['tokens_equal']=summaries['b19']['tokens']==summaries['b24']['tokens']
 (OUT/'compare-b24.json').write_text(json.dumps(comparison)+'\n')
 if comparison['compared']!=1079 or comparison['differ_count'] or comparison['only_one_side'] or comparison['other_fields_differ'] or not comparison['tokens_equal']:
  raise RuntimeError('B19/B24 exactness failure: '+json.dumps(comparison))
 gain=summaries['b19']['prompt_ms']-summaries['b24']['prompt_ms']
 result={'card':'0000:47:00.0','driver':'rank1','profile':0,'prompt_rows':4096,'prefill_rows':256,'decode_steps':48,
  'b19_binary_sha256':sha(BINARIES['b19']),'b24_binary_sha256':sha(BINARIES['b24']),
  'b19_prompt_ms':summaries['b19']['prompt_ms'],'b24_prompt_ms':summaries['b24']['prompt_ms'],
  'b19_minus_b24_prompt_ms':gain,'b24_over_b19_prompt_speedup':summaries['b19']['prompt_ms']/summaries['b24']['prompt_ms'],
  'comparison':comparison,'target_buffers_compared':comparison['compared'],'target_differ_count':comparison['differ_count'],
  'tokens_equal':comparison['tokens_equal'],'mem_available_at_load_gib':admitted,'kernel_faults':0}
 (OUT/'b24-results.json').write_text(json.dumps(result,indent=1)+'\n')
 print(json.dumps({'b19_minus_b24_prompt_ms':gain,'speedup':result['b24_over_b19_prompt_speedup'],'buffers':comparison['compared'],'tokens_equal':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
