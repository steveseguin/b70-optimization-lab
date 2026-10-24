#!/usr/bin/env python3
"""Source derivation only. Does not extract, compile or launch anything."""
from pathlib import Path
import json,hashlib,difflib
D=Path(__file__).resolve().parent;Q=D.parent;L=Q.parent
P=L/'expert-iq3xxs-block/micro'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rep(s,a,b):
 assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def runner():
 old=(P/'runner.cpp').read_text();s=old
 # Numerical data-access kernel is the only operator difference; frozen owner,
 # timing, copies, exact outputs, mismatch retention and shutdown stay intact.
 s=s.replace('963610200','471974600').replace('965690280','474741560').replace('1073741824','536870912')
 s=s.replace('6272000','9216000').replace('627200','921600').replace('321126400','471859200')
 s=s.replace('gsq.iq3xxs-block.native-micro.v1','gsq.iq4nl-direct.native-micro.v1')
 s=s.replace('std::array<Data,3>','std::array<Data,1>').replace('std::array<Case,3>','std::array<Case,1>').replace('i<3','i<1').replace('j<3','j<1').replace('(cycle+j)%3','0')
 s=s.replace('pairs==84&&submissions==168','pairs==28&&submissions==56')
 s=rep(s,'(n==12800||n==40)','(n==51200||n==40)')
 s=s.replace('c.ya=alloc(12800);c.yb=alloc(12800)','c.ya=alloc(51200);c.yb=alloc(51200)')
 s=s.replace('v.x=read(s.x,0,51200,s.x_sha)','v.x=read(s.x,0,12800,s.x_sha)').replace('v.expected=read(s.y,0,12800,s.y_sha)','v.expected=read(s.y,0,51200,s.y_sha)')
 s=s.replace('iq3::valid_route(r,512,640,640)','iq3::valid_route(r,512,2560,2560)')
 start=s.index('  integrated::Matrix m{};');end=s.index('   need(cmd.size()==1',start)
 s=s[:start]+'''  for(unsigned arm=0;arm<2;++arm){std::vector<PreparedCompute>cmd;d.begin_capture(cmd);
   try{auto y=arm?c.yb:c.ya,status=arm?c.sb:c.sa;
    if(arm)gsq_iq4_direct::routed_gemv(d,iq3::Type::IQ4_NL,c.w,c.x,y,c.routes,status,512,2560,640,10,2560,iq3::Type::BF16,iq3::Type::BF16,32,0);
    else iq3::kopt::routed_gemv(d,iq3::Type::IQ4_NL,c.w,c.x,y,c.routes,status,512,2560,640,10,2560,iq3::Type::BF16,iq3::Type::BF16,32,0);
    d.end_capture();}catch(...){d.end_capture();throw;}
'''+s[end:]
 # Insert helper after guard/read/stable stat definitions, outside namespace.
 marker='struct Data{'
 pos=s.index(marker);s=s[:pos]+'}\n#include "startup.hpp"\nnamespace micro {\n'+s[pos:]
 s=rep(s,'d=std::make_unique<Device>(std::move(owner));Harness h','d=std::make_unique<Device>(std::move(owner));await_backend_ack(out);acknowledged=true;Harness h')
 s=rep(s,'bool entered=false,safe=true,passed=false;','bool entered=false,safe=true,passed=false,acknowledged=false;')
 s=rep(s,'\\"profiling\\":true,', '\\"backend_acknowledged\\":\"<<(acknowledged?\"true\":\"false\")<<\",\\"profiling\\":true,')
 return old,s
if __name__=='__main__':
 old,s=runner();(D/'runner.cpp').write_text(s);(D/'runner.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile=str(P/'runner.cpp'),tofile='runner.cpp')))
 selected=(P/'selected.hpp').read_text();selected=selected[:selected.index('#define GSQN_RUNTIME_HEADERS_PROVIDED')]+'#include "../direct.hpp"\n';(D/'selected.hpp').write_text(selected)
 pins={str(p):sha(p) for p in [P/'runner.cpp',P/'selected.hpp',Q/'direct.hpp',Q/'policy.hpp',Q/'evidence/cpu-proof.json',L/'integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/single_device.cpp']}
 (D/'parent-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
 print(json.dumps({'source_only':True,'runner_sha256':sha(D/'runner.cpp'),'startup_sha256':sha(D/'startup.hpp')}))
