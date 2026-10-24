#!/usr/bin/env python3
"""Only narrow fixed-range changes to the frozen candidate suite; no runtime."""
from pathlib import Path
import hashlib,json,difflib
P=Path(__file__).resolve().parent;OLD=P.parent/'operating';ROOT=P.parents[4]
SOURCE_SHA='a11d27d1de412c995de47e8103bf2c345feaa0dc3fbba89525ef5c306f543b85'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def main():
 src=OLD/'generated/suite.py';assert sha(src)==SOURCE_SHA;original=src.read_text();s=original
 s=replace(s,'OPERATING=Path(__file__).resolve().parent.parent',f'OPERATING=Path({str(OLD)!r})\nCOMPLETION=Path(__file__).resolve().parent.parent')
 s=replace(s,'CAP=26','CAP=12')
 s=replace(s,"m['total_requests']==CAP","m['total_requests']==26")
 s=replace(s,"prior=first_native_proof(base['binary_sha256'])","prior=first_native_proof(base['binary_sha256'])\n    V.prerequisites(base['binary_sha256'])")
 s=replace(s,"A=load_adapter()","A=load_adapter()\nv=importlib.util.spec_from_file_location('gsq_attention_completion_checks',COMPLETION/'checks.py');V=importlib.util.module_from_spec(v);v.loader.exec_module(V)")
 s=replace(s,"files=[prior,", "files=[COMPLETION/'prepare.py',COMPLETION/'preparation.json',COMPLETION/'checks.py',COMPLETION/'manifest.json',V.PRIOR,V.STORAGE,prior,")
 s=replace(s,"scope=m['scope']","scope=json.loads((COMPLETION/'manifest.json').read_text())['scope']")
 s=s.replace('measured_requests=24','measured_requests=10').replace('max_output_tokens=24*128+2*8','max_output_tokens=10*128+2*8')
 s=replace(s,"authority='this outer26-request suite owns count/storage policy; inherited adapter2-request comparison helper is not called'","authority='fixed completion prompts7..11 only;12requests/13state dumps; frozen original corpus retained',completion_manifest_sha256=sha(COMPLETION/'manifest.json'),verified_prefix_sha256=V.PRIOR_SHA")
 s=replace(s,"C.bind_references(plan)","V.prerequisites(plan['adapter']['binary_sha256'])\n    require(plan['completion_manifest_sha256']==sha(COMPLETION/'manifest.json') and plan['verified_prefix_sha256']==V.PRIOR_SHA,'completion identity')\n    C.bind_references(plan)")
 s=replace(s,"for i,prompt in enumerate(m['prompts']):","for i,prompt in enumerate(m['prompts'][7:],7):")
 s=replace(s,"len(measured)==12","len(measured)==5")
 s=s.replace('GSQ Q8 p33 candidate; every measured arm checked against frozen baseline','GSQ Q8 p33 completion prompts7..11; every arm exact frozen baseline')
 s=s.replace('candidate correctness and descriptive timing only; separate-process baseline comparison is not a speed promotion','five-pair separate-session correctness only; do not combine timings with interrupted prefix or claim end-to-end speed')
 path=P/'generated/suite.py';path.write_text(s);(P/'overlay.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=str(src),tofile=str(path))))
 r={'passed':True,'source_sha256':{str(src):SOURCE_SHA},'generated_sha256':{str(path):sha(path)},'recipe_sha256':sha(__file__),'patch_sha256':sha(P/'overlay.patch'),'native_execution':False}
 (P/'preparation.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
