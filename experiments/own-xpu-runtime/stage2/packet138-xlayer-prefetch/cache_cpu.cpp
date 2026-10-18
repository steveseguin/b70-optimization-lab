// CPU-only test oracle for the Python LRU model, reusing the frozen 58v policy.
#include "../packet58v-async-cache/native/cache_table.hpp"
extern "C" void* p138_cache_create(const uint64_t* sizes,uint64_t capacity){try{
 std::vector<p58::Expert> experts;
 for(unsigned layer=0;layer<48;++layer)for(unsigned i=0;i<512;++i)
  experts.push_back({0x10000000,0x20000000,0x30000000,sizes[layer]-2,1,1});
 return new p58::Cache(std::move(experts),0x40000000,capacity);
}catch(...){return nullptr;}}
extern "C" void p138_cache_free(void* p){delete static_cast<p58::Cache*>(p);}
extern "C" int p138_cache_step(void* p,const uint32_t* keys,unsigned count,uint32_t* filled,uint64_t* offsets,uint64_t* metrics){try{
 auto&cache=*static_cast<p58::Cache*>(p);std::vector<uint32_t> routes(keys,keys+count);auto plan=cache.prepare(routes);
 for(unsigned i=0;i<plan.fills.size();++i){filled[i]=plan.fills[i].expert;offsets[i]=plan.fills[i].offset;}
 metrics[0]=plan.fills.size();metrics[1]=plan.fill_bytes;metrics[2]=plan.evictions;
 cache.commit(plan.epoch,true,true);metrics[3]=cache.resident_bytes();return 0;
}catch(...){return 1;}}
extern "C" int p138_cache_observe(void*p,const uint32_t*keys,unsigned count){try{
 static_cast<p58::Cache*>(p)->observe(std::vector<uint32_t>(keys,keys+count));return 0;
}catch(...){return 1;}}
