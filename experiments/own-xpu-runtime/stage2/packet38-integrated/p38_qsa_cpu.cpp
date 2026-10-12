// Explicit specialization identity: identical body instantiated by p33r2.cpp.
#include "p33_candidates.hpp"
#include "p30_attention.hpp"
#include <iostream>
template<ng::Op Code> void candidate(p30::attention::Fixture& f){
 auto s=f.shape;s.op=Code;auto a=f.args();std::vector<float> local(round2::local_floats(s)),global(round2::scratch_floats(s));
 for(int g=0;g<round2::groups(s);++g)p33::qsa_group<Code,0,256,2048,1>(s,a,g,global.data(),ng::HostTeam{local.data()});
}
int main(){try{
 unsigned checks=0;std::vector<int> lengths;for(int n=88;n<=152;++n)lengths.push_back(n);lengths.push_back(256);
 uint64_t hash=1469598103934665603ull;
 for(int n:lengths){p30::attention::Fixture original(n-1,n,2048,256),actual=original;
  for(int op:{ng::attention_score,ng::attention_softmax,ng::attention_value}){auto s=original.shape;s.op=op;ng::cpu(s,original.args());}
  candidate<ng::attention_score>(actual);candidate<ng::attention_softmax>(actual);candidate<ng::attention_value>(actual);
  for(int slot:{5,6,7,15}){if(actual.data[slot]!=original.data[slot])throw std::runtime_error("p33 capacity256 mismatch context="+std::to_string(n)+" slot="+std::to_string(slot));++checks;
   for(auto word:actual.data[slot]){hash^=word;hash*=1099511628211ull;}}
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"workloads\":"<<lengths.size()<<",\"capacity\":256,\"budget\":2048,\"tokens\":1,\"stages\":3,\"exact_full_output_score_probability_status\":true,\"diagnostic_fnv64\":"<<hash<<"}\n";
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
