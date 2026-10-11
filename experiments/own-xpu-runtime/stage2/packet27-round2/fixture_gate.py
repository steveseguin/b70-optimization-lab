"""Four fresh CPU processes: two host compilers, identical fixture bytes."""
import hashlib,json,os,subprocess,time,gzip,copy
from pathlib import Path
from cpu_gates import host
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def archive(report):
 raw=(json.dumps(report,indent=2)+'\n').encode();packed=gzip.compress(raw,mtime=0)
 assert gzip.decompress(packed)==raw
 target=P/'evidence/fixture-gates-full.json.gz';target.parent.mkdir(exist_ok=True);target.write_bytes(packed)
 assert gzip.decompress(target.read_bytes())==raw
 result=copy.deepcopy(report)
 for row in result['rows']:
  states=row['receipt'].pop('teardown')
  row['receipt']['teardown_summary']=[{k:v for k,v in state.items() if k!='sequence'}|{'sequence_entries':len(state.get('sequence',[]))} for state in states]
 result['full_receipts']=dict(path=str(target.relative_to(P)),uncompressed_sha256=hashlib.sha256(raw).hexdigest(),compressed_sha256=sha(target),original_bytes=len(raw),compressed_bytes=len(packed),round_trip_bytes_verified=True,original_logical_name='fixture-gates.json before teardown summarization')
 (P/'fixture-gates.json').write_text(json.dumps(result,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 root=B/f'fixtures-{time.time_ns()}';root.mkdir();rows=[];expected=None
 for compiler in ('host','icpx-host'):
  binary=B/compiler/'nongemv-fixtures';host(binary)
  for repeat in range(2):
   out=root/f'{compiler}-{repeat}';cmd=[str(binary),'--fixtures',str(B/'fusion-fixtures'),'--output',str(out)]
   with out.with_suffix('.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
   assert r.returncode==0,out.with_suffix('.log').read_text()[:1500]
   row=json.loads((out/'receipt.json').read_text());assert row['passed'] and row['reference_exact'] and row['packet18_exact'] and not row['device_executed']
   h=sha(out/'output.bin');assert h==row['output_sha256'];assert expected is None or h==expected;expected=h
   rows.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),receipt=row,output_sha256=h));print(compiler,repeat,'PASS',flush=True)
 archive(dict(passed=True,device_executed=False,rows=rows,output_sha256=expected))
if __name__=='__main__':main()
