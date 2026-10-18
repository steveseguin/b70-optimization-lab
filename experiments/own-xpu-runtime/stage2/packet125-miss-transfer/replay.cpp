#include "../packet58j-onecard-port/cache_table.hpp"
#include <array>
#include <fstream>
#include <iostream>
struct Route {uint32_t id,begin,count;};
int main(int argc,char**argv){if(argc!=3)return 1;std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);std::vector<p58::Expert> experts;
for(unsigned l=0;l<48;++l)for(unsigned e=0;e<512;++e){uint64_t g=l==2?704000:524800;experts.push_back({256,512,768,g,g,921600});}
p58::Cache cache(experts,4096,18000000000ull);uint64_t selected_bytes=0,misses=0;unsigned cases=0,zero=0,maxmiss=0;
for(unsigned token=0;token<128;++token){std::array<Route,480> routes;in.read((char*)routes.data(),sizeof(routes));if(!in) return 2;std::vector<uint32_t> ids;bool selected=token%64==0||token%64==15||token%64==31||token%64==63;auto epoch=cache.begin_position();
 for(unsigned layer=0;layer<48;++layer){uint32_t mask=0;unsigned n=0;for(unsigned slot=0;slot<10;++slot){auto r=routes[layer*10+slot];if(r.id>=512||r.begin||r.count!=2560)return 3;auto id=layer*512+r.id;ids.push_back(id);if(!cache.resident(id)){mask|=1u<<slot;++n;}}
  if(selected){uint32_t header[3]={token,layer,mask};out.write((char*)header,sizeof(header));out.write((char*)(routes.data()+layer*10),120);++cases;zero+=n==0;maxmiss=std::max(maxmiss,n);misses+=n;selected_bytes+=n*(layer==2?2329600ull:1971200ull);}}
 cache.finish_position(epoch,true);auto plan=cache.prepare(ids);cache.commit(plan.epoch,true,true);
}char extra;if(in.read(&extra,1))return 4;
std::cout<<"{\"cases\":"<<cases<<",\"zero_miss_cases\":"<<zero<<",\"misses\":"<<misses<<",\"miss_bytes\":"<<selected_bytes<<",\"max_misses\":"<<maxmiss<<",\"simulated_cache\":true}\n";
}
