#!/usr/bin/env python3
"""Source derivation only; no payload read, compiler, plan, owner or device."""
from pathlib import Path
import json,hashlib,difflib
D=Path(__file__).resolve().parent;L=D.parents[1];P=L/'iq4nl-down-direct/micro'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rep(s,a,b):
 assert s.count(a)==1,(a[:120],s.count(a));return s.replace(a,b)
def runner():
 old=(P/'runner.cpp').read_text();s=old
 s=s.replace('9216000','6553600').replace('471974600','6677776').replace('536870912','6712768').replace('474741560','6712768')
 s=s.replace('gsq.iq4nl-direct.native-micro.v1','gsq.hc-bf16-one-sg.native-micro.v1')
 s=rep(s,'struct Data{std::vector<uint8_t>w,x,routes,expected,status;};','struct Data{std::vector<uint8_t>w,x,expected;};')
 s=rep(s,'struct Case{Allocation w,x,routes,ya,yb,sa,sb;','struct Case{Allocation w,x,ya,yb;')
 s=rep(s,'(n==51200||n==40)','(n==640||n==8)')
 start=s.index('  Case c{};');end=s.index('   need(cmd.size()==1',start)
 s=s[:start]+'''  Case c{};c.w=alloc(v.w.size());c.x=alloc(v.x.size());c.ya=alloc(spec.rows*2);c.yb=alloc(spec.rows*2);upload(c.w,v.w);upload(c.x,v.x);
  for(unsigned arm=0;arm<2;++arm){std::vector<PreparedCompute>cmd;d.begin_capture(cmd);
   try{auto y=arm?c.yb:c.ya;
    if(arm)gsq_hc_one_sg::gemv(d,iq3::Type::BF16,c.w,c.x,y,spec.rows,10240,iq3::Type::BF16,iq3::Type::BF16,32,0);
    else iq3::kopt::gemv(d,iq3::Type::BF16,c.w,c.x,y,spec.rows,10240,iq3::Type::BF16,iq3::Type::BF16,32,0);
    d.end_capture();}catch(...){d.end_capture();throw;}
'''+s[end:]
 start=s.index('  std::array<Data,1>data;');end=s.index('  guard();entered=true;',start)
 s=s[:start]+'''  std::array<Data,2>data;for(size_t i=0;i<2;++i){auto&s=fixed[i];original_identity(s);need(s.layer==0&&s.rows==(i?4u:320u),"fixed low/inject cases");
   auto&v=data[i];v.x=read(s.x,0,20480,s.x_sha);v.expected=read(s.y,0,s.rows*2,s.y_sha);
   v.w=read(s.packed,0,size_t(s.rows)*20480,s.weight_sha);original_identity(s);
  }
'''+s[end:]
 s=s.replace('std::array<Case,1>cases','std::array<Case,2>cases').replace('for(size_t i=0;i<1;++i)','for(size_t i=0;i<2;++i)').replace('j<1','j<2').replace('unsigned i=0;auto&c','unsigned i=((cycle/2)+j)%2;auto&c')
 s=rep(s,'auto a=h.output(c.ya),b=h.output(c.yb),sa=h.output(c.sa),sb=h.output(c.sb);bool exact=a==b&&a==data[i].expected&&sa==sb&&sa==data[i].status;','auto a=h.output(c.ya),b=h.output(c.yb);bool exact=a==b&&a==data[i].expected;')
 start=s.index('<<",\\"A_status_sha256');end=s.index('<<",\\"exact',start);s=s[:start]+s[end:]
 s=rep(s,',std::pair{"A-status",&sa},std::pair{"B-status",&sb}','')
 s=s.replace('exact BF16/status baseline gate','exact BF16 baseline gate').replace('pairs==28&&submissions==56','pairs==56&&submissions==112')
 return old,s
if __name__=='__main__':
 old,s=runner();(D/'runner.cpp').write_text(s);(D/'runner.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile=str(P/'runner.cpp'),tofile='runner.cpp')))
 (D/'selected.hpp').write_text((P/'selected.hpp').read_text().replace('../direct.hpp','../one_sg.hpp'))
 for n in ['startup.hpp','handshake.py']:(D/n).write_bytes((P/n).read_bytes())
 files=[P/'runner.cpp',P/'startup.hpp',P/'handshake.py',P/'evidence/device-a/review.json',D.parent/'one_sg.hpp',D.parent/'policy.hpp']
 (D/'parent-pins.json').write_text(json.dumps({str(f):sha(f) for f in files},indent=2)+'\n')
 print(json.dumps(dict(source_only=True,runner_sha256=sha(D/'runner.cpp'),startup_sha256=sha(D/'startup.hpp'))))
