#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace p25 {
template<class Submit,class Wait> auto capture_samples(unsigned n,Submit submit,Wait wait){
 std::vector<decltype(submit())> out;out.reserve(n);for(unsigned r=0;r<n;++r)out.push_back(submit());wait();return out;
}
template<class Visit,class Wait> void sequence48(Visit visit,Wait wait){for(unsigned layer=0;layer<48;++layer)visit(layer);wait();return;}
inline uint64_t duration(uint64_t begin,uint64_t end,uint64_t cap){if(!begin||end<=begin||end-begin>cap)throw std::runtime_error("invalid GPU timestamp or per-submission budget");return end-begin;}
inline unsigned mock_timing_gate(){
 struct Mock {unsigned submitted=0,waits=0,uploads=1,tail=0;std::vector<unsigned> stages;
  unsigned issue(bool staged){if(staged){stages.push_back(++submitted);tail=submitted;}stages.push_back(++submitted);tail=submitted;return tail;}
  void wait(){++waits;return;}
 };
 Mock m;auto samples=capture_samples(200,[&]{return m.issue(true);},[&]{m.wait();});
 if(samples.size()!=200||m.submitted!=400||m.waits!=1||m.uploads!=1||samples.back()!=400)throw std::runtime_error("mock batch/wait/copy count");
 for(unsigned i=0;i<m.stages.size();++i)if(m.stages[i]!=i+1)throw std::runtime_error("mock stage dependency order");
 Mock sequence;sequence48([&](unsigned){sequence.issue(false);},[&]{sequence.wait();});
 if(sequence.submitted!=48||sequence.waits!=1||sequence.uploads!=1)throw std::runtime_error("mock 48-layer sequence");
 unsigned failures=0;for(auto pair:std::vector<std::pair<uint64_t,uint64_t>>{{0,2},{3,3},{3,2},{1,1002}}){try{duration(pair.first,pair.second,1000);}catch(const std::runtime_error&){++failures;}}
 if(failures!=4||duration(1,1001,1000)!=1000)throw std::runtime_error("mock budget boundary");return 7;
}
}
