# Retained ancestor evidence; obsolete entrypoint deliberately refused.
if __name__ == '__main__':
 raise SystemExit('Retired ancestor. Use cpu_gate.py, full_shape.py and startup103.py; see README.md.')
"""Execute each selected composition, twice under GNU and Intel, with exact bytes.
Reuse the parent test vectors while selecting only this view's implementations.
The generated source is retained and bound by hash; production code is untouched.
"""
import json,subprocess,shlex,resource
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices

def generated():
 a=(P/'p73_cpu.cpp').read_text();a=a[:a.index('int main(')]
 a=a.replace('namespace {','int selected_expert=0;bool selected_hc=false;\nnamespace {',1)
 a=a.replace('arm.template operator()<1>("experts2-a");arm.template operator()<2>("experts2-b");','if(selected_expert==0)arm.template operator()<0>("wide64");else if(selected_expert==1)arm.template operator()<1>("experts2-a");else arm.template operator()<2>("experts2-b");')
 a=a.replace('p73hc::host(b);','if(selected_hc)p73hc::host(b);else p60::host_gate_mix(b);')
 b=(P/'p74_cpu.cpp').read_text();b=b[:b.index('int main(')]
 b=b.replace('unsigned cases=0;','bool selected_packed=false;\nunsigned cases=0;')
 b=b.replace('candidate.shape=shape;candidate.run(b);','candidate.shape=shape;if(selected_packed)candidate.run(b);else {b[0]=expanded.data();b[1]=expanded.data();base.run(b);}')
 # Per-view lane sums use the actually selected storage reader.
 b=b.replace('b=p74::lane<T,K>(packed.data()+r*rb,x.data(),range.first,range.second,lane);','b=selected_packed?p74::lane<T,K>(packed.data()+r*rb,x.data(),range.first,range.second,lane):p33::dense_lane<T,K>(expanded.data()+r*er,x.data(),range.first,range.second,lane);')
 prefix='''#include "p65_expert.hpp"
#include "p73_hc.hpp"
#include "p49c_kernel.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
namespace component73 {
'''
 suffix=r'''
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("DENSE HC EXPERTS OUTPUT");
 std::string dense=argv[1],hc=argv[2],experts=argv[3];
 if(dense!="production"&&dense!="head-packed"&&dense!="dense-packed"&&dense!="combined")throw std::runtime_error("dense selection");
 if(hc!="production"&&hc!="hc-wide")throw std::runtime_error("HC selection");
 if(experts!="wide64"&&experts!="experts2-a"&&experts!="experts2-b")throw std::runtime_error("expert selection");
 namespace fs=std::filesystem;fs::path out=argv[4];fs::create_directories(out/"hc-experts");fs::create_directories(out/"dense");
 component73::selected_expert=experts=="wide64"?0:experts=="experts2-a"?1:2;component73::selected_hc=hc=="hc-wide";
 {component73::Recorder r(out/"hc-experts");
 component73::run_shape<iq3::Type::IQ2_S,2560>(r,640,0);component73::run_shape<iq3::Type::IQ4_NL,640>(r,2560,0);
 for(unsigned i=0;i<8;++i){component73::run_shape<iq3::Type::IQ2_S,2560>(r,17,i);component73::run_shape<iq3::Type::IQ4_NL,640>(r,17,i);component73::run_hc(r,i);}
 if(r.count!=26)throw std::runtime_error("selected expert/HC case count");}
 component74::expected.open(out/"dense/expected.bin",std::ios::binary);component74::actual.open(out/"dense/candidate.bin",std::ios::binary);component74::logfile.open(out/"dense/cases.jsonl");
 component74::selected_packed=dense=="head-packed"||dense=="combined";component74::test<iq3::Type::Q6_K,2560,1>();
 component74::selected_packed=dense=="dense-packed"||dense=="combined";
#define T(TYPE,K) component74::test<iq3::Type::TYPE,K,1>();component74::test<iq3::Type::TYPE,K,4>()
 T(Q6_K,2560);T(Q8_0,2560);T(Q6_K,6144);T(Q8_0,6144);T(Q8_0,640);T(Q6_K,10240);T(Q8_0,10240);component74::test<iq3::Type::Q6_K,6144,4,true>();
#undef T
 component74::expected.close();component74::actual.close();component74::logfile.close();
 if(component74::cases!=64)throw std::runtime_error("selected dense case count");
 std::cout<<"90 selected composition cases PASS\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''
 return prefix+a+'\n}\nnamespace component74 {\n'+b+suffix

def main():
 limits();dest=B/'composed-cpu';dest.mkdir(exist_ok=True);source=dest/'composed.cpp';source.write_text(generated())
 report=dict(passed=False,device_executed=False,sources={},views={},commands=[])
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/('fixture-'+compiler);deps=dest/(compiler+'.d')
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(deps),str(source),'-o',str(binary)]
  with (dest/(compiler+'-compile.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  report['commands'].append(cmd)
  for n in shlex.split(deps.read_text().replace('\\\n',' ').split(':',1)[1]):report['sources'][str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for name,v in views().items():
   row=report['views'].setdefault(name,dict(choices=choices(*v),runs=[]))
   for repeat in (1,2):
    out=dest/name/compiler/str(repeat);out.mkdir(parents=True,exist_ok=True)
    command=[str(binary),*v,str(out)]
    with (out/'run.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    for kind in ('expected','candidate'):
     data=json.dumps(choices(*v),sort_keys=True).encode()+b'\n'+b''.join((out/part/(kind+'.bin')).read_bytes() for part in ('hc-experts','dense'))
     (out/(kind+'.bin')).write_bytes(data)
    assert sha(out/'expected.bin')==sha(out/'candidate.bin')
    row['runs'].append(dict(compiler=compiler,repeat=repeat,command=command,path=str(out.relative_to(ROOT)),expected_sha256=sha(out/'expected.bin'),candidate_sha256=sha(out/'candidate.bin'),cases=90))
   print(compiler,name,'two repeats PASS',flush=True)
 for row in report['views'].values():
  assert len(row['runs'])==4 and len({r['candidate_sha256'] for r in row['runs']})==1
  row['passed']=True
 report['sources'][str((P/'composed_cpu.py').relative_to(ROOT))]=sha(P/'composed_cpu.py')
 report.update(passed=True,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence/composed-byte-identity.json',report)
if __name__=='__main__':main()
