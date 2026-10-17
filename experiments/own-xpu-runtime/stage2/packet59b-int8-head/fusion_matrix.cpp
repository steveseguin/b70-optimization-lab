// Actual owner submission, shared device fixture inputs, no validation-only shim.
#include "adapter_fixture.cpp"
#include "small_gemv_fixture.hpp"
#include <iostream>
int main(int argc,char**argv){
 if(argc!=2)return 2;
 unsigned checks=0,failures=0;
 auto cases=adapter_cases();
 Runner runner(0);runner.initialize();auto retained=runner.owned.size();
 std::vector<float> scratch(64*1024*1024);
 std::cout<<"{\"adapter_rows\":[";bool comma=false;
 // Cases 8/9/10 are the exact K2 route+gather construction and its zero/NaN
 // variants. 49 adds the scheduled ni=3 ABI. 6/7 cover both combine norms.
 for(unsigned index:{6,7,8,9,10,49})for(int version:{0,1,2,6}){
  if(index<8&&version>1)continue;
  auto c=cases.at(index);auto expected=c.buffers;
  for(auto& site:c.sites){std::vector<void*> ptr;for(auto id:site.ids)ptr.push_back(expected[id].data.data());
   ptr.insert(ptr.end(),{scratch.data(),expected[c.error].data.data(),expected[c.position].data.data(),expected[c.active].data.data(),expected[c.rope].data.data()});
   integrated::evaluate(site.spec,ptr.data());
  }
  std::vector<Allocation> allocated;for(auto& b:c.buffers)allocated.push_back(runner.upload(b.data));
  // K2 folds BOTH arms, including implementation 0. K1a only folded nonzero.
  unsigned passes=0;
  for(auto site:c.new_sites){site.spec.implementation=version;auto l=packet18::submit_parallel(runner.d,site.spec,runner.binding(site,c,allocated),runner.control,runner.score,runner.probability);passes+=l.passes;runner.finish(l);}
  unsigned mismatches=0;
  for(int id:c.outputs){++checks;auto actual=runner.get(allocated[id],expected[id].data.size());
   if(actual!=expected[id].data){++failures;++mismatches;auto off=std::mismatch(actual.begin(),actual.end(),expected[id].data.begin()).first-actual.begin();
    std::cerr<<"case="<<index<<" version="<<version<<" buffer="<<id<<" byte="<<off<<" actual="<<unsigned(actual[off])<<" expected="<<unsigned(expected[id].data[off])<<'\n';}
  }
  if(comma)std::cout<<',';comma=true;
  std::cout<<"{\"case\":"<<index<<",\"version\":"<<version<<",\"passes\":"<<passes<<",\"mismatches\":"<<mismatches<<"}";
  runner.d.retire_completed_events();while(runner.owned.size()>retained){runner.d.arena.release(runner.owned.back());runner.owned.pop_back();}
 }
 auto stop=runner.d.shutdown(std::chrono::seconds(60));if(!stop.safe_to_exit||stop.exit_code)return 2;
 // All eight registry p39 entries, via p28/p33 producers and actual p39 submit;
 // every scenario from the device fixture, including NaN and blocked controls.
 std::filesystem::create_directories(argv[1]);
 auto p39=p39_fixture_gate(0,argv[1],false);checks+=p39.checks;
 auto small=small_gemv_fixture_gate(0,argv[1]);checks+=small.checks;
 std::cout<<"],\"p39_checks\":"<<p39.checks<<",\"small_checks\":"<<small.checks<<",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"passed\":"<<(failures?"false":"true")<<",\"device_executed\":false}\n";
 return failures?1:0;
}
