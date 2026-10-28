#include "stage2/packet194-expert-diet-engine/router_tie_diagnostic.hpp"
#include "stage2/packet3/step/plan.hpp"
#include <cassert>
#include <iostream>
int main(){flash::Geometry g;g.context=4096;auto p=flash::Builder(g).activation(flash::Scalar::f32).build(std::vector<bool>(48,false));int routes=0,gathers=0,refusals=0;
 auto refuse=[&](flash::Launch l){bool fail=false;try{routertie::site(l);}catch(const std::exception&){fail=true;}assert(fail);++refusals;};
 for(size_t i=0;i<p.launches.size();++i){const auto&l=p.launches[i];
  if(l.op=="route"){
   ++routes;assert(routertie::site(l).empty());assert(i+1<p.launches.size());auto gather=p.launches[i+1];assert(gather.op=="expert_gather");auto prefix=routertie::site(gather);assert(!prefix.empty());++gathers;
   // Exact source main.cpp route+gather fusion: preserve Builder inputs and append route outputs.
   auto fused=l;fused.outputs.push_back(gather.outputs[0]);fused.outputs.push_back(gather.outputs[1]);assert(routertie::site(fused)==prefix);
   auto bad=l;bad.inputs.pop_back();refuse(bad);bad=fused;bad.inputs[1]="position";refuse(bad);bad=fused;bad.outputs[3]=prefix+"wrong";refuse(bad);
   bad=gather;bad.inputs.resize(2);refuse(bad);bad=gather;bad.inputs[1]=prefix+"hc.a.mix";refuse(bad);bad=gather;bad.outputs[2]=prefix+"wrong";refuse(bad);
  }
 }
 assert(routes==48&&gathers==48&&refusals==288);std::cout<<"PASS real flash::Builder 48 route/gather sites, 48 fused equivalents, 288 malformed binding refusals before IO\n";
}
