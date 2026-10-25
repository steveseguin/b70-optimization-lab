// Host-RAM cost of device allocations: one-card context vs a context holding two B70s (2026-10-25).
// Usage: mem_shadow <cards 1|2> <GiB per card>. Prints MemAvailable and the device-related /proc/meminfo fields before
// and after allocating and filling the device memory, then frees it.
#include <sycl/sycl.hpp>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <string>
#include <vector>
static std::map<std::string,long> meminfo(){std::map<std::string,long> m;std::ifstream f("/proc/meminfo");std::string k;long v;std::string unit;
  while(f>>k>>v){std::getline(f,unit);k.pop_back();m[k]=v;}return m;}
int main(int argc,char** argv){
  const int cards=argc>1?std::atoi(argv[1]):2;const double gib=argc>2?std::atof(argv[2]):4;
  std::vector<sycl::device> gpus;for(auto& d:sycl::device::get_devices(sycl::info::device_type::gpu))gpus.push_back(d);
  gpus.resize(std::min<size_t>(gpus.size(),cards));
  sycl::context ctx(gpus);std::vector<sycl::queue> qs;for(auto& d:gpus)qs.emplace_back(ctx,d,sycl::property::queue::in_order{});
  auto before=meminfo();
  std::vector<void*> ptrs;const size_t bytes=size_t(gib*1073741824.0);
  for(auto& q:qs){void* p=sycl::malloc_device(bytes,q);q.memset(p,1,bytes).wait();ptrs.push_back(p);}
  auto after=meminfo();
  std::printf("cards %zu, %.1f GiB each\n",gpus.size(),gib);
  for(const char* k:{"MemAvailable","MemFree","Shmem","Unevictable","Mlocked","GPUActive","GPUReclaim"})
    if(after.count(k))std::printf("  %-13s %+9.2f GiB\n",k,double(after[k]-before[k])/1048576.0);
  for(size_t i=0;i<ptrs.size();++i)sycl::free(ptrs[i],qs[i]);
}
