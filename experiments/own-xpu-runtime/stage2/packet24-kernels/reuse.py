"""Hash proof for packet23 v1 numerical carryover; never qualifies v2."""
import hashlib,json,subprocess,difflib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];S=P.with_name('packet23-fast')
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sha_bytes(p.read_bytes())
def main():
 proof=json.loads((P/'source-proof.json').read_text());commit=proof['source_commit'];base=proof['source_packet']
 def original(name):return subprocess.check_output(['git','show',commit+':'+base+'/'+name])
 rows=[]
 for name in ['kernels.hpp','core_v2.hpp','detmath.hpp','rope.hpp','rope.bf16','arithmetic.hpp','gemv_batch.cpp','performance.cpp','runtime_kernels.cpp','runtime_kernels.hpp']:
  old=original(name);assert (P/name).read_bytes()==old,name;rows.append(dict(path=name,sha256=sha_bytes(old),identical=True))
 old=original('adapter.cpp').decode();current=(P/'adapter.cpp').read_text();prefix=current.index('#include "adapter.hpp"');current=current[prefix:]
 current=current.replace('Launch submit_parallel_v1(','Launch submit_parallel(').replace('Launch submit_chain_v1(','Launch submit_chain(').replace('Launch submit_rank_v1(','Launch submit_rank(').replace('#include "adapter_v2.inc"','')
 assert ''.join(current.split())==''.join(old.split()),'v1 adapter body changed'
 rows.append(dict(path='adapter.cpp',original_sha256=sha_bytes(old.encode()),candidate_sha256=sha(P/'adapter.cpp'),proof='all original tokens identical after stripping only new header includes, v1 entry suffixes, and appended v2 include'))
 def body(text,anchor):
  pos=text.index(anchor);start=text.index('{',pos);depth=1;end=start+1
  while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
  return text[pos:end]
 oldmain=original('main.cpp').decode();newmain=(P/'main.cpp').read_text()
 regions=[]
 for anchor in ['void make_schedule(){','void fused_batch(const Task& task){','void fused_non_gemv(const Task& task){']:
  oldbody=body(oldmain,anchor);newbody=body(newmain,anchor).replace(' && !a.fixture_resident','')
  assert oldbody==newbody,anchor
  regions.append(dict(region=anchor,sha256=sha_bytes(oldbody.encode()),fixture_only_condition_removed=anchor.startswith('void fused_non')))
 assert 'bool fixture_resident = false;' in newmain and '"--fixture-resident"' not in newmain
 delta=''.join(difflib.unified_diff(oldmain.splitlines(True),newmain.splitlines(True),fromfile='packet23/main.cpp',tofile='packet24/main.cpp'))
 (P/'main-carryover.patch').write_text(delta)
 cpu=json.loads((S/'cpu-tests.json').read_text());carried=cpu['real_model']
 result=dict(passed=True,applies_only_to='--kernels v1',does_not_qualify_v2=True,source_commit=commit,source_packet=base,unchanged=rows,main_numerical_regions=regions,main_diagnostic_and_fixture_delta_sha256=sha(P/'main-carryover.patch'),prior_cpu_receipt_sha256=sha(S/'cpu-tests.json'),prior_carryover_proof_sha256=sha(S/'carryover-proof.json'),original_real_model_receipts=carried,device_executed=False)
 (P/'carryover-proof.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':main()
