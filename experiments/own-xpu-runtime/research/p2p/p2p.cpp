// Cross-card latency microbenchmark (B70): peer copy and host-staged copy of activation-sized buffers between two
// cards selected by PCI address, plus an event round-trip. Reports median microseconds over many repetitions.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <string>
#include <vector>
using clk=std::chrono::steady_clock;
static double us(clk::time_point a,clk::time_point b){return std::chrono::duration<double,std::micro>(b-a).count();}
static double median(std::vector<double> v){std::sort(v.begin(),v.end());return v[v.size()/2];}
int main(int argc,char** argv){
  if(argc<3){std::fprintf(stderr,"usage: p2p BDF_A BDF_B\n");return 2;}
  std::vector<sycl::device> pick(2);int found=0;
  for(auto& d:sycl::device::get_devices(sycl::info::device_type::gpu)){
    if(!d.has(sycl::aspect::ext_intel_pci_address))continue;auto bdf=d.get_info<sycl::ext::intel::info::device::pci_address>();
    for(int i=0;i<2;++i)if(bdf==argv[1+i]){pick[i]=d;++found;}
  }
  if(found!=2){std::fprintf(stderr,"devices not found (%d)\n",found);return 3;}
  sycl::queue a(pick[0],sycl::property::queue::in_order{}),b(pick[1],sycl::property::queue::in_order{});
  std::printf("A %s\nB %s\npeer access A->B %d, B->A %d\n",argv[1],argv[2],int(pick[0].ext_oneapi_can_access_peer(pick[1])),int(pick[1].ext_oneapi_can_access_peer(pick[0])));
  const int reps=400;
  for(size_t bytes:{size_t(4096),size_t(40960),size_t(163840),size_t(655360)}){
    auto* da=sycl::malloc_device<unsigned char>(bytes,a);auto* db=sycl::malloc_device<unsigned char>(bytes,b);auto* host=sycl::malloc_host<unsigned char>(bytes,a);
    a.memset(da,1,bytes).wait();b.memset(db,0,bytes).wait();
    std::vector<double> peer,staged,kernel;
    for(int r=0;r<reps;++r){ // peer copy issued on B's queue reading A's memory, waited on host
      auto t0=clk::now();try{b.memcpy(db,da,bytes).wait();}catch(const sycl::exception& e){std::printf("peer copy failed: %s\n",e.what());break;}peer.push_back(us(t0,clk::now()));}
    for(int r=0;r<reps;++r){ // device A -> pinned host -> device B, both waited (the engine's current path is similar)
      auto t0=clk::now();a.memcpy(host,da,bytes).wait();b.memcpy(db,host,bytes).wait();staged.push_back(us(t0,clk::now()));}
    for(int r=0;r<reps;++r){ // empty kernel on A then on B, each waited: the sync floor of a cross-card hand-off
      auto t0=clk::now();a.single_task([]{}).wait();b.single_task([]{}).wait();kernel.push_back(us(t0,clk::now()));}
    std::printf("%7zu B  peer %8.1f us  staged %8.1f us  two waited kernels %8.1f us\n",bytes,peer.empty()?-1.:median(peer),median(staged),median(kernel));
    sycl::free(da,a);sycl::free(db,b);sycl::free(host,a);
  }
  return 0;
}
