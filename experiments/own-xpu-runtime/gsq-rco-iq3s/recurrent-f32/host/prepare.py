#!/usr/bin/env python3
"""Source-only Host closure using current corrected private sources."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;F=P.parent;L=F.parent;R=F.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if __name__=='__main__':
 m=json.loads((F/'evidence/materialization.json').read_text());old=L/'integration/evidence/full-host-build.json';h=json.loads(old.read_text());assert h['passed'] and h['mode']=='host'
 base=F/'build/source-v2';main=base/'experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp';assert str(main.relative_to(R)) in m['generated_sha256']
 entry=P/'entry.cpp';assert not entry.exists();entry.write_text('#define main packet26_model_entry\n#include "'+str(main)+'"\n#undef main\nint main(int argc,char**argv){std::vector<char*> args{argv[0]};bool f32=false,mini=false,gsq=false;for(int i=1;i<argc;++i){std::string_view x(argv[i]);if(x=="--recurrent-f32")f32=true;else args.push_back(argv[i]);mini|=x=="--mini";gsq|=x=="--gsq-packed";}if(!f32||!mini||!gsq)return 64;args.push_back(nullptr);return packet26_model_entry(int(args.size()-1),args.data());}\n')
 sources={'entry':str(entry)}
 for name,path in h['sources'].items():
  if name=='entry':continue
  f=base/path;assert str(f.relative_to(R)) in m['generated_sha256'];sources[name]=str(f)
 assert len(sources)==32
 support=L/'integration/host-support/device_validation.hpp';assert sha(support)==h['source_sha256'][str(support.relative_to(R))]
 p={'status':'SOURCE_ONLY_NOT_COMPILED','materialization_sha256':sha(F/'evidence/materialization.json'),'parent_host_build_sha256':sha(old),'sources':sources,'translation_units':32,'objects_reused':0,'flags':h['commands'][0][:h['commands'][0].index('-MMD')],'additional_sources':{str(entry):sha(entry),str(support):sha(support),str(Path(__file__)):sha(Path(__file__))},'scope':'Actual corrected Engine and synthetic mini geometry; no real model or device backend'}
 (P/'preparation.json').write_text(json.dumps(p,indent=2)+'\n');print(sha(P/'preparation.json'))
