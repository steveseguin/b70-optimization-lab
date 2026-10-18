"""Extract only the two HC kernels from the linked AOT report; CPU file reads."""
import gzip,json,re
from build_engine import P,limits
from build_layer import sha
ROOT=P.parents[3]
def main():
 limits();r=json.loads((P/'evidence/registers.json').read_text());rows=[]
 for n,h in r['sources'].items():assert sha(ROOT/n)==h,n
 for k in r['kernels']:
  if not any(x in k['name'] for x in ('p73hc','p117hc')):continue
  assert sha(P/k['assembly'])==k['sha256']
  blocks=[]
  for z in r['zeinfo']:
   assert sha(P/z['path'])==z['sha256']
   text=gzip.decompress((P/z['path']).read_bytes()).decode().split('\nkernels_misc_info:')[0]
   blocks += [b for b in re.split(r'\n  - name:\s*',text)[1:] if b.splitlines()[0].strip()==k['name'].removeprefix('//.kernel ')]
  assert len(blocks)==1
  block=blocks[0];private=bool(re.search('per_thread_memory_buffers|scratch_size|spill_size|private_size',block))
  rows.append(dict(mode='p117' if 'p117hc' in k['name'] else 'production',grf=k['grf'],scratch_messages=k['scratch_messages'],spill_metadata=k['spill_metadata'],per_thread_memory_allocated=private,eu_thread_count=int(re.search(r'eu_thread_count:\s*(\d+)',block)[1]),barrier_count=int(re.search(r'barrier_count:\s*(\d+)',block)[1]),assembly=k['assembly'],sha256=k['sha256']))
 assert len(rows)==2 and all(x['grf']==128 and not x['spill_metadata'] and not x['scratch_messages'] and not x['per_thread_memory_allocated'] for x in rows)
 report=dict(passed=True,device_executed=False,report_sha256=sha(P/'evidence/registers.json'),kernels=rows,note='Linked offline image only; no hardware occupancy measurement. Other emitted unused router kernels are outside this HC audit.')
 (P/'evidence/hc-register-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
