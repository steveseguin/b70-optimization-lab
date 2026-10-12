#!/usr/bin/env python3
"""Serial missing receipt producers. CPU only; invoke through seal40 recorder."""
import argparse,hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
from seal40 import P,B,sha,save
from storage import admit
PY=sys.executable
PROMPTS=('incident-retrospective','code-review','customer-email','benchmark-analysis')
def run(command,timeout=600):
 command=['nice','-n','19','ionice','-c','3',*map(str,command)]
 result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
 if result.returncode:raise RuntimeError('CPU gate failed '+str(command)+'\n'+result.stdout[-2000:]+result.stderr[-4000:])
 return result

def native():
 rows=[]
 for suffix,gate_suffix in (('test','cpu'),('asan','asan'),('tsan-llvm22','tsan')):
  binary=B/('native-controller-'+suffix);receipt=P/('native-controller-'+gate_suffix+'.json')
  result=run([PY,'-B',P/'native_controller_gate.py','--binary',binary,'--output',receipt])
  row=json.loads(receipt.read_text());assert row['passed'] and row['binary_sha256']==sha(binary)
  assert row['cases']==1123 and row['ternary_patterns']==1093 and row['long_random_cases']==24
  rows.append(dict(receipt=receipt.name,sha256=sha(receipt),binary_sha256=sha(binary)))
  binary=B/('native-mailbox-fault-'+suffix);result=run([binary]);raw=json.loads(result.stdout)
  assert raw['passed'] and raw['gates']==5 and raw['repeated_requests']==32
  name='native-mailbox-faults'+('' if suffix=='test' else '-'+gate_suffix)+'.json'
  raw.update(device_executed=False,binary_sha256=sha(binary),source_sha256={name:sha(P/name) for name in ('native_controller.hpp','native_controller_test.cpp','native_mailbox_fault_test.cpp')},stderr=result.stderr)
  save(P/name,raw);rows.append(dict(receipt=name,sha256=sha(P/name),binary_sha256=sha(binary)))
 save(P/'native-sanitizer-aggregate40.json',dict(passed=True,device_executed=False,rows=rows,tests=6,source_sha256={'qualification_extra40.py':sha(P/'qualification_extra40.py')}))

def p38k2():
 names=('test_k2_selection','test_k2_admission','test_p38_k2')
 suite=unittest.defaultTestLoader.loadTestsFromNames(names)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 receipt=dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),sources_sha256={name:sha(P/name) for name in ('qualification_extra40.py','k2_summary.py','k2-class-registry.json',*(n+'.py' for n in names))})
 save(P/'p38-k2-selection-tests.json',receipt)
 if not result.wasSuccessful():raise RuntimeError('p38 K2 aggregate failed')

def bounded_hash(file,offset,size):
 h=hashlib.sha256()
 with file.open('rb') as stream:
  stream.seek(offset);remaining=size
  while remaining:
   data=stream.read(min(4*1024*1024,remaining))
   if not data:raise ValueError('short authenticated input '+str(file))
   remaining-=len(data);h.update(data)
 return h.hexdigest()

def integrity():
 import prepare_mtp
 checks={};sources={};inp=json.loads((B/'input/input.json').read_text());checks['input/input.json']=sha(B/'input/input.json')
 for name,digest in inp['files'].items():assert sha(B/'input'/name)==digest;checks['input/'+name]=digest
 for line in (B/'input/identity.tsv').read_text().splitlines():
  name,*fields=line.split();file=Path(inp['model_dir'])/name;st=file.stat()
  assert tuple(map(int,fields))==(st.st_size,st.st_dev,st.st_ino,st.st_mtime_ns,st.st_ctime_ns),'target file metadata changed '+name
  checks['target-stat/'+name]=hashlib.sha256(line.encode()).hexdigest()
 assert sha(Path(inp['prompt']))==inp['prompt_sha256'];checks['target-prompt']=inp['prompt_sha256']
 official=json.loads((P/'official-tensors.json').read_text());contract=P.parent/'packet1/tensor-contract.json'
 assert sha(contract)==official['contract_sha256'];checks['official-contract']=sha(contract)
 for name,row in official['files'].items():
  file=prepare_mtp.MODEL/name;before=file.stat();digest=sha(file);after=file.stat()
  identity=lambda st:(st.st_size,st.st_dev,st.st_ino,st.st_mtime_ns,st.st_ctime_ns)
  assert identity(before)==identity(after) and digest==row['sha256'],'official shard changed '+name
  assert (after.st_size,after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns)==tuple(row[k] for k in ('bytes','dev','ino','mtime_ns','ctime_ns'))
  checks['official-file/'+name]=digest;print('authenticated official shard',name,flush=True)
 manifest={line.split()[0]:line.split() for line in (P/'mtp-manifest.tsv').read_text().splitlines()}
 assert len(manifest)==len(official['tensors'])==3101
 for name,row in official['tensors'].items():
  file=prepare_mtp.MODEL/row['shard'];digest=bounded_hash(file,row['file_offset'],row['bytes']);fields=manifest[name]
  assert digest==row['sha256']==fields[7] and fields[1]==row['shard'] and int(fields[2])==row['file_offset'] and int(fields[3])==row['bytes'],name
  checks['official-tensor/'+name]=digest
 for prompt in PROMPTS:
  receipt=P/f'capture-input-{prompt}.json';row=json.loads(receipt.read_text());table=B/f'capture-{prompt}.tsv'
  assert sha(table)==row['table_sha256'];checks['capture-table/'+prompt]=sha(table)
  for name,digest in row['streams'].items():
   assert sha(B/('captured-'+prompt)/name)==digest;checks['capture-stream/'+prompt+'/'+name]=digest
  checks['capture-input/'+prompt]=sha(receipt)
 for name in ('qualification_extra40.py','prepare_mtp.py','prepare.py'):sources[name]=sha(P/name)
 save(P/'resume-input-integrity.json',dict(passed=True,device_executed=False,checked_hashes=len(checks),checks_sha256=checks,source_sha256=sources,official_manifest_sha256=sha(P/'mtp-manifest.tsv'),input_sha256=sha(B/'input/input.json'),maximum_read_chunk_bytes=4*1024*1024,scope='Fresh target bundle/prompt/stat identity, official draft publisher contract and all shard/tensor bytes, and every imported target capture stream; no accelerator opened'))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('native','p38k2','integrity'));a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and 1<=int(os.environ.get('OMP_NUM_THREADS','0'))<=4
 admit(32_000_000)
 {'native':native,'p38k2':p38k2,'integrity':integrity}[a.phase]()
if __name__=='__main__':main()
