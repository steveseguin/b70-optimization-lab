// TP host-side question (2026-10-25): in one shared context, can two host threads (one per card) submit at full rate
// in parallel, and what does a cross-thread, cross-card hand-off cost (thread A publishes its kernel's event, thread
// B submits a peer copy depending on it, then a kernel)? Timing only; the copies are bitwise and checked once.
// Run with ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZE_AFFINITY_MASK=0,3 (cards 23:00.0 and 47:00.0 on steve-b70s).
#include <sycl/sycl.hpp>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>
using clk=std::chrono::steady_clock;
static double us(clk::time_point a,clk::time_point b){return std::chrono::duration<double,std::micro>(b-a).count();}
int main(){
  std::vector<sycl::device> g;for(auto& d:sycl::device::get_devices(sycl::info::device_type::gpu))g.push_back(d);
  if(g.size()<2){std::printf("need 2 GPUs\n");return 1;}
  sycl::context ctx({g[0],g[1]});
  sycl::queue qa(ctx,g[0],sycl::property::queue::in_order{}),qb(ctx,g[1],sycl::property::queue::in_order{});
  const size_t n=2560;float* a=sycl::malloc_device<float>(n,qa);float* b=sycl::malloc_device<float>(n,qb);float* b_in=sycl::malloc_device<float>(n,qb);
  qa.fill(a,1.f,n).wait();qb.fill(b,2.f,n).wait();qb.fill(b_in,0.f,n).wait();
  auto kern=[&](sycl::queue& q,float* p,std::vector<sycl::event> deps={}){return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){p[i]=p[i]*0.5f+1.f;});});};
  const int N=2000;
  // 1. one thread, one queue
  for(int pass=0;pass<2;++pass){auto t=clk::now();for(int i=0;i<N;++i)kern(qa,a);auto e=clk::now();qa.wait();
    if(pass)std::printf("1 thread, 1 card:  enqueue %.2f us/kernel, total %.2f us/kernel\n",us(t,e)/N,us(t,clk::now())/N);}
  // 2. one thread alternating two queues
  for(int pass=0;pass<2;++pass){auto t=clk::now();for(int i=0;i<N;++i){kern(qa,a);kern(qb,b);}auto e=clk::now();qa.wait();qb.wait();
    if(pass)std::printf("1 thread, 2 cards: enqueue %.2f us/kernel, total %.2f us per kernel pair\n",us(t,e)/(2*N),us(t,clk::now())/N);}
  // 3. two threads, one queue each
  for(int pass=0;pass<2;++pass){std::atomic<int> go{0};double ea=0,eb=0;
    auto run=[&](sycl::queue& q,float* p,double& enq){while(!go.load()){}auto t=clk::now();for(int i=0;i<N;++i)kern(q,p);enq=us(t,clk::now())/N;q.wait();};
    auto t=clk::now();std::thread ta(run,std::ref(qa),a,std::ref(ea)),tb(run,std::ref(qb),b,std::ref(eb));go=1;ta.join();tb.join();
    if(pass)std::printf("2 threads, 2 cards: enqueue A %.2f / B %.2f us/kernel, total %.2f us per kernel pair\n",ea,eb,us(t,clk::now())/N);}
  // 4. cross-thread hand-off: A kernel -> publish event -> B (other thread) copy A->B depending on it, then B kernel.
  for(int pass=0;pass<2;++pass){
    std::vector<sycl::event> published(N);std::atomic<int> ready{-1};double total=0;
    std::thread tb([&]{for(int i=0;i<N;++i){while(ready.load(std::memory_order_acquire)<i){}
        auto c=qb.submit([&](sycl::handler& h){h.depends_on(published[i]);h.memcpy(b_in,a,n*4);});kern(qb,b_in,{c});}qb.wait();});
    auto t=clk::now();
    for(int i=0;i<N;++i){published[i]=kern(qa,a);ready.store(i,std::memory_order_release);}
    qa.wait();tb.join();total=us(t,clk::now())/N;
    if(pass)std::printf("cross-thread hand-off chain: %.2f us per (A kernel + B copy + B kernel)\n",total);
  }
  std::vector<float> ha(n),hb(n);qa.memcpy(ha.data(),a,n*4).wait();qb.memcpy(b_in,a,n*4).wait();qb.memcpy(hb.data(),b_in,n*4).wait();
  std::printf("peer copy bitwise: %s\n",std::memcmp(ha.data(),hb.data(),n*4)?"DIFFER":"equal");
}
