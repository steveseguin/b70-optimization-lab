#!/usr/bin/env python3
import argparse,json,os,statistics,subprocess,sys,time
from pathlib import Path
ROOT=Path('/dev/shm/ownrt-lab-r0-c47')
RESEARCH=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/rank0-iq4-c47')
BASE=Path('/dev/shm/ownrt-lab-r0/runs/launch-bp-all.json')
DRIVER=RESEARCH/'tp_rank0_driver.py'
PAT='Fault response|CAT error|engine reset|GPU HANG|wedged|Timedout'

def faults(since):
 p=subprocess.run(['journalctl','-k','--since',f'@{int(since)}','--no-pager'],text=True,capture_output=True)
 lines=[x for x in p.stdout.splitlines() if any(s.lower() in x.lower() for s in PAT.split('|'))]
 return lines

def one(name,mode,profile):
 if (ROOT/'HALT').exists():raise RuntimeError('HALT present')
 start=time.time();before=faults(start-3600)
 if before:
  (ROOT/'HALT').touch();raise RuntimeError('fault lines before run: '+repr(before))
 d=json.loads(BASE.read_text())
 binary='/dev/shm/engine-build-lab-r0-c47-iq4sg16b/sc117-engine' if mode=='new' else '/dev/shm/engine-build-lab-r0-b/sc117-engine'
 for i,a in enumerate(d['argv']):
  if a.endswith('/sc117-engine'):d['argv'][i]=binary
 env=d['environment'];env['FilterBdfPath']='0000:47:00.0'
 env.pop('OWNRT_DRAFT_ATTN_OUT',None)
 if mode=='new':env['OWNRT_EXPERTS_V2_IQ4NL']='2'
 else:env.pop('OWNRT_EXPERTS_V2_IQ4NL',None)
 if profile:env['OWNRT_DECODE_PROFILE']='2'
 else:env.pop('OWNRT_DECODE_PROFILE',None)
 launch=ROOT/f'launch-{name}.json';launch.write_text(json.dumps(d,indent=1)+'\n')
 out=ROOT/'runs'/name
 cmd=['env','-u','LD_PRELOAD','-u','ONEAPI_DEVICE_SELECTOR','flock','/dev/shm/card47.lock','nice','-n','10','taskset','-c','8-15,24-31','python3','-B',str(DRIVER),'run','--launch',str(launch),'--out',str(out),'--steps','48','--prompt','4096','--rows','256','--cache',str(ROOT/'cache')]
 with (ROOT/'runs'/f'{name}.out').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
 lines=faults(start)
 (ROOT/'runs'/f'{name}.faults').write_text('\n'.join(lines)+'\n')
 if lines:
  (ROOT/'HALT').touch();raise RuntimeError(f'GPU fault after {name}: {lines}')
 if rc:raise RuntimeError(f'{name} failed rc={rc}; see {out}.out')
 s=json.loads((out/'summary.json').read_text());med=lambda v:statistics.median(v)
 print(json.dumps({'name':name,'mode':mode,'profile':profile,'half_ms':med(s['half_ms']),'draft_ms':med(s['draft_ms']),'rc':rc,'faults':len(lines)}),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('mode',choices=['ref','new']);ap.add_argument('--profile',action='store_true');a=ap.parse_args();one(a.name,a.mode,a.profile)
if __name__=='__main__':main()
