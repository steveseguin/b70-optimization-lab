#!/usr/bin/env python3
"""One authorized model load, OFF/ON independent contexts; never retries."""
from pathlib import Path
import hashlib,json,os,subprocess,time,struct,math,sys
HERE=Path(__file__).resolve().parent
ROOT=Path('/dev/shm/sc117-reference-prefix178-cpu-20261028-r1/model')
MODEL=Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert not ROOT.exists(),'fresh exclusive case; no automatic retry'
 build=json.loads((HERE/'compiled-identity.json').read_text());assert sha(build['binary'])==build['binary_sha256']
 for group in ('sources','static_library_sha256'):
  for p,h in build[group].items():assert sha(p)==h,p
 old=json.loads((HERE.parent/'capture-source-identity.json').read_text())
 source_root=HERE.parents[3]
 resolved_old_pins={}
 for p,h in old['source_hashes'].items():
  path=Path(p) if Path(p).is_absolute() else source_root/p
  assert sha(path)==h,str(path)
  resolved_old_pins[str(path)]=h
 identity=json.loads((HERE/'identity.json').read_text());assert sha(HERE/'input.json')==identity['input_sha256']
 tokens=json.loads((HERE/'input.json').read_text())['tokens'];assert len(tokens)==178 and hashlib.sha256(struct.pack('<178i',*tokens)).hexdigest()==identity['prefix_le_i32_sha256']
 mem={k:int(v.split()[0])*1024 for k,v in (x.split(':',1)for x in Path('/proc/meminfo').read_text().splitlines())};assert mem['MemAvailable']>=80*1024**3,'80GiB startup floor'
 if sys.argv[1:]==['--preflight-only']:
  print(json.dumps({'preflight_passed':True,'model_loaded':False,'output_created':False,'source_root':str(source_root),'resolved_old_source_pins':resolved_old_pins,'MemAvailable':mem['MemAvailable']},indent=2));return
 assert not sys.argv[1:],'only optional --preflight-only accepted'
 ROOT.mkdir();env=os.environ.copy()
 for k in ('GGML_CPU_EXACT_ACC','GGML_CPU_EXACT_ROPE','GGML_CPU_EXACT_ROUND'):env.pop(k,None)
 env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8',EXACT_CAPTURE_LAYERS='1',EXACT_NEUTRALITY_TWO_CONTEXTS='1')
 cmd=['nice','-n','19','taskset','-c','8-15',build['binary'],str(MODEL),str(HERE/'input.json'),str(ROOT),'8']
 modelstat={str(p):{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'inode':p.stat().st_ino}for p in sorted(MODEL.parent.glob('*.gguf'))}
 rec={'argv':cmd,'environment':{k:v for k,v in env.items()if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},'started':time.time(),'MemAvailable':mem['MemAvailable'],'model_files':modelstat,'build':build,'wrapper_sha256':sha(__file__)};(ROOT/'run.json').write_text(json.dumps(rec,indent=2)+'\n')
 with (ROOT/'log.txt').open('w')as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec.update(returncode=rc,finished=time.time());(ROOT/'run.json').write_text(json.dumps(rec,indent=2)+'\n');assert rc==0,'failure retained; no retry/capture acceptance'
 neutrality=json.loads((ROOT/'neutrality.json').read_text());assert neutrality['full_logits_bitwise_equal']
 assert (ROOT/'off/logits-177.f32').read_bytes()==(ROOT/'on/logits-177.f32').read_bytes()
 files={}
 for p in ROOT.rglob('*'):
  if p.is_file():files[str(p.relative_to(ROOT))]={'bytes':p.stat().st_size,'sha256':sha(p)}
 for layer in range(48):
  assert files[f'on/layer-{layer:02d}.f32']['bytes']==40960
  for field,n in [('input',2560),('logits',512),('probabilities',512),('ids',10),('weights',10)]:
   f=ROOT/f'on/layer-{layer:02d}-{field}.{"i32"if field=="ids"else"f32"}';data=f.read_bytes();assert len(data)==n*4
   values=struct.unpack('<'+str(n)+('i'if field=='ids'else'f'),data);assert all(0<=x<512 for x in values)if field=='ids'else all(math.isfinite(x)for x in values)
 assert len(list((ROOT/'on').glob('layer-*')))==288
 layouts=[json.loads(x)for x in (ROOT/'on/router-layouts.jsonl').read_text().splitlines()];assert len(layouts)==240
 receipt={'schema':'ownrt.prefix178.cpu-capture-receipt.v1','passed':True,'input_json_sha256':identity['input_sha256'],'packed_prompt_sha256':identity['prefix_le_i32_sha256'],'tokens':178,'position':177,'off':str(ROOT/'off'),'on':str(ROOT/'on'),'root':str(ROOT),'files':files,'capture_counts':{'layers':48,'router_arrays':240,'router_nodes':192},'full_logits_bitwise_equal':True,'process_returncode':rc,'run_sha256':sha(ROOT/'run.json'),'neutrality':neutrality,'expected_argmax':None,'scope':'One loaded model/two fresh sequential contexts; same178prefix. No comparison to244batch bitwise identity or overall quality resolution.'}
 (ROOT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS178 full-logit OFF/ON equality and48+240captures',flush=True)
if __name__=='__main__':main()
