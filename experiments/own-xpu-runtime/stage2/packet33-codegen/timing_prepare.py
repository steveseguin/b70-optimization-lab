#!/usr/bin/env python3
"""Generate focused timing harness from p29; never runs a device executable."""
import hashlib,json,subprocess,shlex,os
from pathlib import Path
P=Path(__file__).resolve().parent; R=P.parent/'packet29-merged'; B=P/'build'
def replace(s,a,b):
 if s.count(a)!=1:raise ValueError('unmatched transformation '+a[:100])
 return s.replace(a,b)
def main():
 B.mkdir(exist_ok=True)
 src=(R/'fixture_driver.cpp').read_text()
 src='#define PACKET26_K2\n#include "p33r2.hpp"\n#include "p33_stop.hpp"\n'+src
 src=src.replace('std::filesystem::path(__FILE__).parent_path()/"rope.bf16"', 'std::filesystem::path("'+str(R/'rope.bf16')+'")')
 src=src.replace('std::filesystem::path(__FILE__).parent_path()/"build/fusion-fixtures"','std::filesystem::path("'+str(R/'build/fusion-fixtures')+'")')
 src=src.replace('unsigned card=0,seed=1,repetitions=200;', 'p33::install_stop(); unsigned card=0,seed=1,repetitions=200;')
 src=replace(src,'if(implementation==2&&round2::supported(s))','if(implementation==3&&round2::supported(s))launch=p33r2::submit(device,s,bindings,scratch);\n   else if(implementation==2&&round2::supported(s))')
 a=src.index('const std::set<std::string> decode_names{');b=src.index(';',a)
 src=src[:a]+'const std::set<std::string> decode_names{"qsa-attention-1.fixture"}'+src[b:]
 src=replace(src,'int incumbent=(source.shape.op==ng::norm||source.shape.op==ng::combine_norm||source.shape.op==ng::route_gather)?1:0;','int incumbent=2;')
 src=replace(src,'int alternative=round2::supported(source.shape)?2:specialised::supported(source.shape)?1:0;','int alternative=3;')
 src=replace(src,'std::string candidate=alternative==2?"round2":"specialised";','std::string candidate="p33.qsa.shape";')
 src=src.replace('implementation==2?"round2":implementation==1?"specialised":"packet18"','implementation==3?"p33.qsa.shape":implementation==2?"round2":implementation==1?"specialised":"packet18"')
 src=replace(src,'auto small=small_gemv_timing_gate(card,out);','AdapterFixtureReceipt small{0,0,R"({"safe_to_exit":true,"skipped":true})"};')
 # Standalone timing is not the p29 all-class gate; do not retain misleading gate counts.
 src=src.replace('packet26.k2.v1','packet33.k2.v1')
 src=src.replace('\\"odd_lengths\\":20,\\"ties\\":1,\\"nan_routes\\":1','\\"odd_lengths\\":0,\\"ties\\":0,\\"nan_routes\\":0')
 src=src.replace('alternative==2?"round2":alternative==1?"specialised":"packet18"','alternative==3?"p33.qsa.shape":alternative==2?"round2":alternative==1?"specialised":"packet18"')
 src=src.replace('incumbent==1?"specialised":"packet18"','incumbent==2?"round2":incumbent==1?"specialised":"packet18"')
 src=src.replace('try{fixture_validation::inject_failure','try{p33::check_stop();fixture_validation::inject_failure')
 src=src.replace('catch(const std::exception& e){if(fixture_validation::only','catch(const std::exception& e){if(p33::stop_requested)throw;if(fixture_validation::only')
 src=src.replace(r'\"passed\":true,\"device_executed\":',r'\"passed\":"<<(all_exact?"true":"false")<<",\"device_executed\":')
 src=src.replace('std::cout<<checks<<" fixture checks PASS\\n";return 0;', 'std::cout<<checks<<" fixture checks complete; exact="<<all_exact<<std::endl;return all_exact?0:1;')
 (B/'timing_main.cpp').write_text(src)
 src=(R/'adapter_fixture.cpp').read_text();src='#include "p33r2.hpp"\n#include "p33_stop.hpp"\n'+src
 src=src.replace('std::filesystem::path(__FILE__).parent_path()/"rope.bf16"', 'std::filesystem::path("'+str(R/'rope.bf16')+'")')
 src=replace(src,'for(auto& [label,c]:cases){bool has_round2=', 'for(auto& [label,c]:cases){if(label!="route")continue;bool has_round2=')
 src=src.replace('runner.candidate=has_round2?"round2":"specialised";', 'runner.candidate="p33.route.rank4";')
 src=src.replace('runner.implementation=version&&has_round2?"round2":"specialised";', 'runner.implementation=version?"p33.route.rank4":"specialised";')
 src=src.replace('version&&has_round2?"round2":"specialised"', 'version?"p33.route.rank4":"specialised"')
 old='runner.finish(packet18::submit_parallel(runner.d,site.spec,runner.binding(site,c,allocated),runner.control,runner.score,runner.probability));}runner.events=nullptr;'
 new='if(version){auto launch=p33r2::submit_simple(runner.d,site.spec,runner.binding(site,c,allocated));runner.finish(launch);}else runner.finish(packet18::submit_parallel(runner.d,site.spec,runner.binding(site,c,allocated),runner.control,runner.score,runner.probability));}runner.events=nullptr;'
 src=replace(src,old,new)
 src=src.replace('try{fixture_validation::inject_failure','try{p33::check_stop();fixture_validation::inject_failure')
 src=src.replace('catch(const std::exception& e){if(fixture_validation::only','catch(const std::exception& e){if(p33::stop_requested)throw;if(fixture_validation::only')
 (B/'timing_adapter.cpp').write_text(src)
 flags=['-std=gnu++20','-O2','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl']
 includes=['-I'+str(x) for x in (P,R,R/'../../stage1/packet3-prep/src',R/'../packet2/kernels',R/'../packet2/loader')]
 cmds=[]
 for name in ('timing_main','timing_adapter'):
  argv=['/opt/intel/oneapi/compiler/2026.0/bin/icpx',*flags,*includes,'-c',str(B/(name+'.cpp')),'-o',str(B/(name+'.o'))]
  with (B/(name+'.log')).open('w') as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT)
  cmds.append(dict(argv=argv,returncode=r.returncode))
  if r.returncode:raise RuntimeError(name+' compile failed')
 (P/'timing-build.json').write_text(json.dumps(cmds,indent=2)+'\n')
if __name__=='__main__':main()
