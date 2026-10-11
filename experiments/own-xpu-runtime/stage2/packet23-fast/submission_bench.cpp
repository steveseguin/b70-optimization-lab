#include "owner.hpp"
#include "mock_device.hpp"
#include <iostream>
#include <algorithm>
struct Null final:ownrt::Operation {};
struct Mock final:ownrt::MockDevice {
 ownrt::Event compute(const ownrt::Operation&,std::span<void* const>,std::span<const ownrt::Event> deps)override{return marker(deps);}
};
int main(){
 ownrt::Device d(std::make_unique<Mock>());std::vector<ownrt::Allocation> all;
 for(int i=0;i<2048;++i)all.push_back(d.arena.allocate("buffer"+std::to_string(i),4,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction));
 std::vector<ownrt::Allocation> bound;for(int i=0;i<19;++i)bound.push_back(all[1800+i]);
 Null op;std::vector<double> samples;
 for(int r=0;r<11;++r){auto start=std::chrono::steady_clock::now();ownrt::Event tail=0;
  for(int n=0;n<876;++n)tail=d.compute(op,bound,{});
  auto us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/876;
  if(r)samples.push_back(us);if(!d.wait(tail,std::chrono::seconds(60)))return 1;d.retire_completed_events();
 }
 std::sort(samples.begin(),samples.end());std::cout<<"{\"median_us_per_submission\":"<<(samples[4]+samples[5])/2<<",\"submissions_per_segment\":876,\"bindings\":19,\"allocations\":2048,\"device_executed\":false}\n";
 return !d.shutdown(std::chrono::seconds(60)).safe_to_exit;
}
