#!/usr/bin/env python3
"""Adapt frozen bundle adapter and complete candidate suite; metadata only."""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[2];R=L.parents[2]
OLD=L/'qkv-q6-p33/engine/operating';B=L/'state-bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():assert sha(f)==h,f
 out=P/'generated';assert not out.exists();out.mkdir();patch=[];outputs={}
 for src,name in [(B/'generated/adapter.py','adapter.py'),(OLD/'generated/suite.py','suite.py')]:
  original=src.read_text();s=original
  if name=='adapter.py':
   s=replace(s,'CANDIDATE=P.parent','CANDIDATE=P.parent.parent')
   s=replace(s,'BUNDLE=load(P.parent/\'reader.py\',',"BUNDLE=load(Path("+repr(str(B/'reader.py'))+"),")
   s=replace(s,"P.parent/'reader.py'","Path("+repr(str(B/'reader.py'))+")")
   s=replace(s,"cmd.extend(['--attention-q8-p33','--qkv-q6-p33'])","cmd.extend(['--attention-q8-p33','--qkv-q6-p33','--expert-iq3xxs-block'])")
   s=replace(s,'request_cap=2,','request_cap=26,')
   s=replace(s,'3*(221743168+9699332) # initial blank RESET plus two requests','27*(221743168+9699332) # initial blank RESET plus all26 requests')
   s=replace(s,"'request_count':2,","'request_count':26,")
   s=replace(s,'raw_state+64*1024**2','raw_state+128*1024**2')
  else:
   s=s.replace('gsq_combined_candidate_checks','gsq_iq3_block_checks')
   s=replace(s,'GSQ combined attention/Q6 QKV p33 candidate; every measured arm checked against frozen baseline','GSQ IQ3_XXS block candidate; every measured arm checked against frozen baseline')
   s=s.replace('+64*1024**2','+128*1024**2')
   s=replace(s,'count=0;measured=[];warm=[];start=time.monotonic()','count=0;measured=[];warm=[];capture_stamps={};start=time.monotonic()')
   s=replace(s,'destination=t.out/name;A.reset(t,destination);count+=1','destination=t.out/name;A.reset(t,destination);count+=1\n        C.verify_capture_stamps(t.out,capture_stamps)')
   s=replace(s,"if measuring:row['metric']=metric(result,cap);row['state_sha256']=A.state_hashes(t)","if measuring:\n            row['metric']=metric(result,cap);row['state_sha256']=A.state_hashes(t);capture_stamps[name]=C.capture_stamp(destination)")
   s=replace(s,"require(count==CAP and len(measured)==12,'incomplete suite')","require(count==CAP and len(measured)==12,'incomplete suite')\n    final=measured[-1]['arms'][-1]\n    require(A.state_hashes(t)==final['state_sha256'],'final explicit DUMP differs')\n    C.verify_capture_stamps(t.out,capture_stamps)")
   s=replace(s,'return dict(passed=True,rank_pids=[p.pid for p in t.children],requests=count,','return dict(passed=True,capture_stamps=capture_stamps,final_explicit_DUMP_verified=True,rank_pids=[p.pid for p in t.children],requests=count,')
   s=replace(s,"result=run_attached(t,plan,m);t.close(True);path=t.out/'resident-suite.json';A.save(path,result)","result=run_attached(t,plan,m);t.close(True);C.verify_capture_stamps(t.out,result['capture_stamps']);result['closed_capture_stamps_verified']=True;path=t.out/'resident-suite.json';A.save(path,result)")
  dest=out/name;dest.write_text(s);outputs[str(dest.relative_to(R))]=sha(dest)
  patch.extend(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=str(src.relative_to(R)),tofile=str(dest.relative_to(R))))
 (P/'overlay.patch').write_text(''.join(patch))
 r=dict(schema='gsq.iq3xxs-block.operating.source.v1',source_sha256={str(Path(f).relative_to(R)):h for f,h in pins.items()},generated_sha256=outputs,recipe_sha256=sha(__file__),patch_sha256=sha(P/'overlay.patch'),device_executed=False,requests=26,retained_state_dumps=27,metadata_forecast_bytes=128*1024**2)
 (P/'preparation.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
