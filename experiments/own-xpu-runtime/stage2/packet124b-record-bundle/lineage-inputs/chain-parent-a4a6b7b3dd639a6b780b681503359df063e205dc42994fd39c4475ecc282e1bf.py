"""Fresh selected-dispatch draft host/reference identity; no historical arithmetic gate."""
import argparse,base64,fcntl,gzip,hashlib,json,os,subprocess,time
from pathlib import Path
from storage import admit,discard,digest,verify_archive
P=Path(__file__).resolve().parent;B=P/'build'
PROMPTS=('incident-retrospective','code-review','customer-email','benchmark-analysis')
PATTERNS=('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin')
def save(path,row):
 admit(2_000_000);path.write_text(json.dumps(row,indent=2)+'\n')
def inventory(root):return {str(f.relative_to(root)):digest(f) for pattern in PATTERNS for f in root.glob(pattern)}
def archived_capture(run):
 """Verify archive content, returning hash metadata plus the small row logs."""
 archive=P/run['scratch_archive']['path']
 assert digest(archive)==run['scratch_archive']['sha256'],'capture archive changed'
 verify_archive(archive);prefix=str(Path(run['output']).relative_to(P))+'/'
 table={};text={};current=None;data=None
 wanted={'draft-rows.jsonl','draft-capture.jsonl','receipt.json'}
 with gzip.open(archive,'rt') as source:
  assert json.loads(next(source))=={'schema':'packet38.scratch-stream.v1'}
  for line in source:
   row=json.loads(line)
   if row['kind']=='file':
    assert row['path'].startswith(prefix);name=row['path'][len(prefix):]
    assert name not in table;table[name]=row;current=name;data=bytearray() if name in wanted else None
   elif row['kind']=='chunk' and data is not None:data.extend(base64.b64decode(row['base64'],validate=True))
   elif row['kind']=='end':
    if data is not None:text[current]=data.decode()
    current=None;data=None
 assert set(text)==wanted,'capture archive missing rows/receipt'
 return table,text
def inputs(name):
 receipt=P/f'capture-input-{name}.json';row=json.loads(receipt.read_text());table=B/f'capture-{name}.tsv';root=B/('captured-'+name)
 assert digest(table)==row['table_sha256']
 assert digest(root/'target-rows.json')==row['target_rows_sha256']
 assert all(digest(root/n)==h for n,h in row['streams'].items())
 # Input provenance stays bound to immutable packet31 target outputs.
 original=json.loads((P.parent/'packet36-draft'/receipt.name).read_text())
 assert row['streams']==original['streams'] and row['target_rows_sha256']==original['target_rows_sha256']
 return table,row
def execute_owner(command,root,row,timeout=43500):
 """Keep output absent until the binary creates it; archive only after exit."""
 assert not root.exists(),'capture output must not already exist'
 log=root.with_name(root.name+'.log');owned_log=False
 try:
  with log.open('x') as output:
   owned_log=True
   result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
  row['returncode']=result.returncode
  receipt=root/'receipt.json'
  if not receipt.is_file():raise RuntimeError(f'capture owner exited {result.returncode} without receipt.json; startup log retained')
  result_row=json.loads(receipt.read_text())
  assert result.returncode==0 and result_row['passed'] and result_row['device_executed'] is False,'capture owner failed'
  assert len(result_row['teardown'])==1 and all(t['safe_to_exit'] and not t['live_bytes'] and not t['in_flight'] for t in result_row['teardown'])
  fixtures=inventory(root);assert fixtures,'empty captured fixture inventory'
  row.update(passed=True,fixture_sha256=fixtures,fixture_bytes=sum(f.stat().st_size for pattern in PATTERNS for f in root.glob(pattern)))
 except BaseException as error:
  row.update(passed=False,error=str(error));raise
 finally:
  # subprocess.run returns/raises only after this CPU owner has exited/reaped.
  # A parse/startup failure may not create output; create evidence only now.
  if owned_log:
   root.mkdir(exist_ok=True);log.replace(root/'capture.log')
   row['scratch_archive']=discard(root)
def one(name,mode,dispatch):
 table,input_row=inputs(name);binary=B/mode/'own-rt-iq3'
 from cpu_gates import host
 host(binary);admit(160_000_000)
 inp=json.loads((B/'input/input.json').read_text())
 root=B/f'draft40-{name}-{mode}-{time.time_ns()}'
 cmd=['nice','-n','19','ionice','-c','3',str(binary),'--draft-capture',str(table),'--rank','1','--context','256','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--model-dir',inp['model_dir'],'--output',str(root),'--dispatch',str(dispatch),'--seconds','43200']
 row=dict(passed=False,device_executed=False,output=str(root),binary_sha256=digest(binary),compiler=mode,dispatch_sha256=digest(dispatch),table_sha256=digest(table),command=cmd)
 try:
  execute_owner(cmd,root,row)
  assert digest(binary)==row['binary_sha256'] and digest(dispatch)==row['dispatch_sha256'],'capture binary/dispatch changed during execution'
 except BaseException as error:
  row.update(passed=False,error=str(error));raise
 finally:
  save(P/f'capture40-{name}-{mode}.json',row)
 return row
def _capture(name):
 dispatch=P/'dispatch-p38.json'
 sources={n:digest(P/n) for n in ('capture40.py','main.cpp','mtp.hpp','dispatch-p38.json')}
 first=one(name,'gnu-host',dispatch);reference=one(name,'icpx-host',dispatch)
 assert first['fixture_sha256']==reference['fixture_sha256'],'selected-kernel host/reference fixture mismatch'
 first_table,first_text=archived_capture(first);ref_table,ref_text=archived_capture(reference)
 assert first_text['draft-capture.jsonl']==ref_text['draft-capture.jsonl'],'draft proposals differ'
 keys=('draft_position','confirmed_token','head','guess')
 rows=[json.loads(s) for s in first_text['draft-rows.jsonl'].splitlines()]
 refs=[json.loads(s) for s in ref_text['draft-rows.jsonl'].splitlines()]
 assert [{k:r[k] for k in keys} for r in rows]==[{k:r[k] for k in keys} for r in refs]
 assert sources=={n:digest(P/n) for n in sources},'capture sources changed during host/reference execution'
 first['source_sha256']=sources;save(P/f'capture-run-{name}.json',first)
 repeat=dict(passed=True,device_executed=False,prompt=name,binary_sha256=first['binary_sha256'],host_reference_binary_sha256=reference['binary_sha256'],reference_compiler='icpx-host',dispatch_sha256=digest(dispatch),files=len(first['fixture_sha256']),sha256=first['fixture_sha256'],source_sha256=sources,reference_receipt_sha256=digest(P/f'capture40-{name}-icpx-host.json'),reference_scratch_archive=reference['scratch_archive'],scope='Fresh GNU host and Intel host reference use the identical selected dispatch; all sample, full-vocabulary logit, cache and control bytes match. No equality to historical draft arithmetic is assumed.')
 save(P/f'capture-repeat-{name}.json',repeat)
 prior=json.loads((P.parent/'packet31-mtp-acceptance/acceptance.json').read_text())
 targets={r['draft_position']:r for r in prior['positions'] if r['prompt']==name};assert len(targets)==64
 predictions={r['draft_position']:r['guess'] for r in rows}
 report=[]
 for pos,target in targets.items():
  key=f'row-{pos}/logits.bf16';assert key in first['fixture_sha256'] and first_table[key]['sha256']==ref_table[key]['sha256']
  token=predictions[pos];report.append(dict(position=pos,generated_index=target['generated_index'],target_token=target['target_token'],draft_token=token,hit=token==target['target_token'],logits_sha256=first['fixture_sha256'][key],reference_logits_sha256=ref_table[key]['sha256'],exact_full_vocabulary=True))
 save(P/f'agreement-{name}.json',dict(passed=True,device_executed=False,prompt=name,positions=64,binary_sha256=first['binary_sha256'],host_reference_binary_sha256=reference['binary_sha256'],dispatch_sha256=digest(dispatch),rows=report,target_acceptance=sum(r['hit'] for r in report)/64,exact_repeat_receipt_sha256=digest(P/f'capture-repeat-{name}.json'),source_sha256=sources,scope=repeat['scope'],historical_distances='Packet36/38 FP8 and INT8 distance reports remain historical; they are not reused as current arithmetic qualification.'))
 print(name,'PASS fresh selected-dispatch full-byte host/reference identity',flush=True)
def capture(name):
 with (B/'cpu-mtp.lock').open('a') as lock:
  fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
  _capture(name)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('prompt',choices=(*PROMPTS,'all'));a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and 1<=int(os.environ.get('OMP_NUM_THREADS','0'))<=4
 for name in PROMPTS if a.prompt=='all' else (a.prompt,):capture(name)
if __name__=='__main__':main()
