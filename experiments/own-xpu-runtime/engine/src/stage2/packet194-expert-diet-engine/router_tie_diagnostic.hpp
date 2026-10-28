#pragma once
// Opt-in reference-implementation diagnostic, not a production tie definition.
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <vector>
namespace routertie {
inline void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
using Scores=std::array<float,512>;using IDs=std::array<int32_t,10>;using Routes=std::array<int32_t,30>;using Weights=std::array<float,10>;
struct Decision{IDs ids;Routes routes,down;int changed=0;};
inline Decision prepare(const Scores& logits,const Scores& probabilities,const IDs& host_old,const IDs& actual,const Weights& weights,const Routes& routes,const Routes& down){
 for(size_t i=0;i<512;++i)need(std::isfinite(logits[i])&&std::isfinite(probabilities[i])&&probabilities[i]>=0,"router tie finite scores/probabilities");
 need(host_old==actual,"router tie actual/host original IDs disagree");
 for(int i=0;i<10;++i){need(actual[i]>=0&&actual[i]<512&&std::isfinite(weights[i])&&weights[i]>=0,"router tie selected extent/value");for(int j=0;j<i;++j)need(actual[i]!=actual[j],"router tie duplicate ID");need(routes[i*3]==actual[i]&&routes[i*3+1]==0&&routes[i*3+2]==640&&down[i*3]==actual[i]&&down[i*3+1]==0&&down[i*3+2]==2560,"router tie actual route bindings");}
 // Exactly the registered reference comparator; equal-key order is toolchain-specific.
 std::vector<int32_t> order(512);std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return probabilities[a]>probabilities[b];});
 Decision d{actual,routes,down};
 for(int i=0;i<10;++i){int old=actual[i],next=order[i];if(old==next)continue;need(std::bit_cast<uint32_t>(logits[old])==std::bit_cast<uint32_t>(logits[next]),"router tie refuses unequal raw score words");need(probabilities[old]==probabilities[next],"router tie probability equality");d.ids[i]=next;d.routes[i*3]=next;d.down[i*3]=next;++d.changed;}
 for(int i=0;i<10;++i)for(int j=0;j<i;++j)need(d.ids[i]!=d.ids[j],"router tie candidate duplicate");
 return d;
}
// All decision validation completes before the first upload callback. Exceptions
// during uploads poison the outer request; no fallback or retry is permitted.
template<class Write> inline void publish(const Decision& d,Write write){if(d.changed){write(0,d.ids.data(),sizeof(d.ids));write(1,d.routes.data(),sizeof(d.routes));write(2,d.down.data(),sizeof(d.down));}}
} // namespace routertie
