#!/usr/bin/env python3
import argparse,hashlib,json,statistics,subprocess,time
from pathlib import Path
ROOT=Path('/dev/shm/ownrt-lab-r0-c47')
RESEARCH=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/rank0-iq4-c47')
BASE=Path('/dev/shm/ownrt-lab-r0/runs/launch-bp-all.json')
DRIVER=RESEARCH/'tp_rank0_driver.py'
BINARY=Path('/dev/shm/engine-build-svc-b19-gdnprep-20261026/sc117-engine')
SHA='51f32b2655cc0a9d514081362ea6b3ceaa8b0d004df94fbbd83eb7fa76e3ae0a'
PAT='Fault response|CAT error|engine reset|GPU HANG|wedged|Timedout'
MIN_AVAILABLE=35*1024**3

def faults(since):
 p=subprocess.run(['journalctl','-k','--since',f'@{int(since)}','--no-pager'],text=True,capture_output=True)
 return [x for x in p.stdout.splitlines() if any(s.lower() in x.lower() for s in PAT.split('|'))]

def available():
 for line in Path('/proc/meminfo').read_text().splitlines():
  if line.startswith('MemAvailable:'):return int(line.split()[1])*1024
 raise RuntimeError('MemAvailable missing')

def one(name,mode):
 if (ROOT/'HALT').exists():raise RuntimeError('HALT present')
 if hashlib.sha256(BINARY.read_bytes()).hexdigest()!=SHA:raise RuntimeError('B19 binary hash mismatch')
 avail=available()
 if avail<MIN_AVAILABLE:raise RuntimeError(f'35-GiB admission failed: MemAvailable={avail}')
 start=time.time();before=faults(start-3600)
 if before:
  (ROOT/'HALT').touch();raise RuntimeError('fault lines before run: '+repr(before))
 d=json.loads(BASE.read_text())
 for i,a in enumerate(d['argv']):
  if a.endswith('/sc117-engine'):d['argv'][i]=str(BINARY)
 env=d['environment'];env['FilterBdfPath']='0000:47:00.0';env.pop('OWNRT_DRAFT_ATTN_OUT',None);env.pop('OWNRT_EXPERTS_V2_IQ4NL',None);env.pop('OWNRT_DECODE_PROFILE',None)
 if mode=='on':env['OWNRT_GDN_PREP']='1'
 else:env.pop('OWNRT_GDN_PREP',None)
 launch=ROOT/f'launch-{name}.json';launch.write_text(json.dumps(d,indent=1)+'\n')
 out=ROOT/'runs'/name
 cmd=['env','-u','LD_PRELOAD','-u','ONEAPI_DEVICE_SELECTOR','flock','/dev/shm/card47.lock','nice','-n','10','taskset','-c','8-15,24-31','python3','-B',str(DRIVER),'run','--launch',str(launch),'--out',str(out),'--steps','48','--prompt','4096','--rows','256','--cache',str(ROOT/'cache')]
 with (ROOT/'runs'/f'{name}.out').open('w') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
 lines=faults(start);(ROOT/'runs'/f'{name}.faults').write_text('\n'.join(lines)+'\n')
 if lines:
  (ROOT/'HALT').touch();raise RuntimeError(f'GPU fault after {name}: {lines}')
 if rc:raise RuntimeError(f'{name} failed rc={rc}; see {out}.out')
 s=json.loads((out/'summary.json').read_text());med=lambda v:statistics.median(v)
 print(json.dumps({'name':name,'gdn_prep':mode,'mem_available_start':avail,'half_ms':med(s['half_ms']),'draft_ms':med(s['draft_ms']),'rc':rc,'faults':len(lines)}),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('mode',choices=['off','on']);a=ap.parse_args();one(a.name,a.mode)
