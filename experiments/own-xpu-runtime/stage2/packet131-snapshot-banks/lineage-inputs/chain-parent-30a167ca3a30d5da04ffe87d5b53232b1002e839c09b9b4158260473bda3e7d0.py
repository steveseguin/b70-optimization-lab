"""CPU-only authentication rejection and teardown tests; official files untouched."""
import json,os,subprocess,tempfile
from pathlib import Path
from pipeline import P,sha
from cpu_gates import host
B=P/'build'
def main():
 binary=B/'gnu-host/own-rt-iq3';host(binary)
 inp=json.loads((B/'input/input.json').read_text());rows=(P/'mtp-manifest.tsv').read_text().splitlines();reports=[]
 with tempfile.TemporaryDirectory(dir=B,prefix='draft-auth-') as temp:
  root=Path(temp);table=root/'empty.tsv';table.write_text('')
  for name,expected in (('missing','draft manifest missing'),('truncated','missing official draft tensors'),('hash','official draft tensor SHA256 mismatch'),('identity','official draft file changed')):
   manifest=root/(name+'.tsv')
   if name=='truncated':manifest.write_text('\n'.join(rows[:-1])+'\n')
   elif name in ('hash','identity'):
    modified=[]
    for line in rows:
     fields=line.split();fields[7 if name=='hash' else 9]='0'*64 if name=='hash' else '0';modified.append('\t'.join(fields))
    manifest.write_text('\n'.join(modified)+'\n')
   out=root/name
   command=[str(binary),'--rank','1','--draft-capture',str(table),'--draft-manifest',str(manifest),'--context','256','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--model-dir',inp['model_dir'],'--output',str(out)]
   run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   receipt=json.loads((out/'receipt.json').read_text())
   assert run.returncode==1 and receipt['passed'] is False and receipt['device_executed'] is False and expected in receipt['error']
   assert len(receipt['teardown'])==1 and all(t['safe_to_exit'] and not t['in_flight'] and not t['live_bytes'] for t in receipt['teardown'])
   failure=json.loads((out/'failure-before-teardown.json').read_text())
   reports.append(dict(case=name,expected=expected,receipt=receipt,failure_before_teardown=failure))
 result=dict(passed=True,device_executed=False,binary_sha256=sha(binary),cases=len(reports),rows=reports)
 (P/'draft-auth-gates.json').write_text(json.dumps(result,indent=2)+'\n');print('4 draft authentication rejection/teardown gates PASS')
if __name__=='__main__':main()
