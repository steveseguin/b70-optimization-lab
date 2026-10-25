// Cross-card hand-off cost without host waits (2026-10-25): two B70s in one SYCL context, one in-order queue each.
// A "step" is: a kernel on card A writes a 40 KB activation block, a peer copy moves it to card B, a kernel on card B
// consumes it (depends on the copy's event, no host wait), and the same back. N round trips are enqueued up front;
// the host waits once at the end. Compared with the same chain done with a host wait after every copy, and with the
// two kernels alone on one card (the compute floor). Exactness is not at stake here (copies are bit copies); only time.
#include <sycl/sycl.hpp>
#include <chrono>
#include <cstdio>
#include <vector>
int main(){
  std::vector<sycl::device> gpus;for(auto& d:sycl::device::get_devices(sycl::info::device_type::gpu))gpus.push_back(d);
  if(gpus.size()<2){std::printf("need two GPUs, found %zu\n",gpus.size());return 1;}
  sycl::context ctx({gpus[0],gpus[1]});
  sycl::queue qa(ctx,gpus[0],sycl::property::queue::in_order{}),qb(ctx,gpus[1],sycl::property::queue::in_order{});
  std::printf("A: %s\nB: %s\n",gpus[0].get_info<sycl::info::device::name>().c_str(),gpus[1].get_info<sycl::info::device::name>().c_str());
  for(size_t bytes:{size_t(4096),size_t(40960),size_t(163840)}){
    const size_t n=bytes/4;
    float* a=sycl::malloc_device<float>(n,qa);float* a_in=sycl::malloc_device<float>(n,qa);
    float* b=sycl::malloc_device<float>(n,qb);float* b_in=sycl::malloc_device<float>(n,qb);
    qa.fill(a,1.f,n).wait();qb.fill(b,2.f,n).wait();qa.fill(a_in,0.f,n).wait();qb.fill(b_in,0.f,n).wait();
    auto kernel=[&](sycl::queue& q,float* out,const float* in,std::vector<sycl::event> deps){
      return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){out[i]=in[i]*0.5f+1.f;});});};
    const int N=200;
    // 1. device-event chain: A kernel -> copy A->B -> B kernel -> copy B->A -> A kernel ...
    for(int warm=0;warm<2;++warm){
      auto t0=std::chrono::steady_clock::now();sycl::event last;
      for(int i=0;i<N;++i){
        auto ka=kernel(qa,a,a_in,i==0?std::vector<sycl::event>{}:std::vector<sycl::event>{last});
        auto ca=qb.submit([&](sycl::handler& h){h.depends_on(ka);h.memcpy(b_in,a,bytes);});
        auto kb=kernel(qb,b,b_in,{ca});
        last=qa.submit([&](sycl::handler& h){h.depends_on(kb);h.memcpy(a_in,b,bytes);});
      }
      last.wait();double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      if(warm)std::printf("%7zu B  device-event chain: %7.1f us per round trip (2 kernels + 2 peer copies)\n",bytes,us);
    }
    // 2. host-waited chain: wait after every copy
    for(int warm=0;warm<2;++warm){
      auto t0=std::chrono::steady_clock::now();
      for(int i=0;i<N;++i){kernel(qa,a,a_in,{}).wait();qb.memcpy(b_in,a,bytes).wait();kernel(qb,b,b_in,{}).wait();qa.memcpy(a_in,b,bytes).wait();}
      double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      if(warm)std::printf("%7zu B  host-waited chain:  %7.1f us per round trip\n",bytes,us);
    }
    // 3. compute floor: the two kernels back to back on one card, no copies
    for(int warm=0;warm<2;++warm){
      auto t0=std::chrono::steady_clock::now();
      for(int i=0;i<N;++i){kernel(qa,a,a_in,{});kernel(qa,a_in,a,{});}
      qa.wait();double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      if(warm)std::printf("%7zu B  one-card floor:     %7.1f us per 2 kernels\n",bytes,us);
    }
    sycl::free(a,qa);sycl::free(a_in,qa);sycl::free(b,qb);sycl::free(b_in,qb);
  }
}
