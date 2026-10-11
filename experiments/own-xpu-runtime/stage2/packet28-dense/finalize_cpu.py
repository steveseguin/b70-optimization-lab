"""Consolidate CPU receipts, readelf/nm capture gate, and deterministic repeats."""
import hashlib,json,subprocess,re,resource,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,r):Path(p).write_text(json.dumps(r,indent=2)+'\n')
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 evidence={}
 for mode in ('host','icpx-host'):
  for task in ('validation','fixtures'):
   for repeat in (1,2):
    folder=B/mode/(task+str(repeat))
    for name in ('receipt.json','exactness.jsonl','validation-entries.jsonl'):
     f=folder/name
     if f.is_file():evidence[str(f.relative_to(B))]=f.read_text()
 blob=json.dumps(evidence,sort_keys=True).encode();(P/'cpu-harness-evidence.json.gz').write_bytes(gzip.compress(blob,mtime=0))
 records=[]
 for mode in ('host','icpx-host'):
  binary=B/mode/'g2';dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
  assert not any(x in dynamic.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
  for task in ('validation','fixtures'):
   values=[];hashes=[]
   for repeat in (1,2):
    folder=B/mode/(task+str(repeat));r=load(folder/'receipt.json');assert r['passed'] and not r['device_executed'] and r['live_bytes']==0 and r['in_flight']==0
    output=folder/('exactness.jsonl' if task=='fixtures' else 'validation-entries.jsonl');hashes.append(sha(output));values.append({k:r[k] for k in ('checks','negative_validation_checks')})
   assert hashes[0]==hashes[1] and values[0]==values[1]
   records.append(dict(compiler=mode,task=task,fresh_process_repeats=2,output_sha256=hashes[0],binary_sha256=sha(binary),**values[0]))
 dense=load(P/'dense-cpu-receipt.json');experts=load(P/'expert-build-receipt.json')
 for v in dense['gates'].values():assert v['passed'] and v['fresh_process_repeats']==2
 for v in experts:assert v['same_output_repeats'] and all(x['finite_and_nan_category_passed'] for x in v['outputs'])
 nm=subprocess.check_output(['nm','-S','--defined-only',str(B/'device/g2')],text=True)
 sizes=[int(line.split()[1],16) for line in nm.splitlines() if 'capture_size' in line and len(line.split())>=4]
 assert sizes and max(sizes)<=1024
 # A compile-time failing closure proves the guard rejects oversized arguments.
 test=B/'oversized.cpp';test.write_text('#include "'+str(P/'kernel_guard.hpp')+'"\nint main(){char bytes[1025]{};auto f=p28_guard::checked([=]{return bytes[0];});return f();}\n')
 cmd=['/usr/bin/g++','-std=c++20','-fsyntax-only',str(test)]
 r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode and 'device kernel capture exceeds 1024 bytes' in r.stderr
 (P/'oversized-capture.log').write_text(r.stderr);test.unlink()
 guard=dict(passed=True,capture_symbols=len(sizes),maximum_capture_bytes=max(sizes),negative_compile_guard_passed=True)
 save(P/'kernel-sizes.json',guard)
 protocol=load(P/'protocol-tests.json');assert protocol['passed']
 out=dict(passed=True,device_executed=False,strict_exceptional_output_bit_identity=False,same_card_strict_gate_pending=True,host_compilers=2,fresh_process_repeats_per_compiler=2,arithmetic_checks_per_process=dense['gates']['gcc']['checks']+experts[0]['outputs'][0]['checks'],family_validation_checks_per_process=experts[0]['outputs'][0]['validation_checks'],harness=records,protocol_tests=protocol['tests'],kernel_guard=guard,receipt_hashes={x:sha(P/x) for x in ('dense-cpu-receipt.json','expert-build-receipt.json','protocol-tests.json','kernel-sizes.json','cpu-harness-evidence.json.gz')})
 save(P/'cpu-tests.json',out)
if __name__=='__main__':main()
