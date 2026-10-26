// One bounded packed/predecoded comparison. Synthetic full-size tensor, real
// SC117 gate/up geometry, varied resident routes, no event profiling or flush.
#define KERNEL_GUARD_SKIP
#include "kernel.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <random>

namespace {
volatile std::sig_atomic_t stop_requested=0;
void request_stop(int signal){stop_requested=signal;}
struct CooperativeStop {};
}

int main() try {
 using namespace iq3_predecoded;
 constexpr uint32_t rows=640,columns=2560,slots=10,experts=512,cases=64,samples=6;
 constexpr size_t inputs=size_t(cases)*slots*columns,outputs=size_t(cases)*slots*rows;
 std::signal(SIGINT,request_stop);std::signal(SIGTERM,request_stop);
 const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(60);
 auto check_stop=[&]{if(stop_requested||std::chrono::steady_clock::now()>=deadline)throw CooperativeStop{};};
 std::setvbuf(stdout,nullptr,_IOLBF,0);
 std::mt19937 rng(1701);
 std::vector<uint8_t> packed(size_t(experts)*rows*(columns/256)*packed_bytes);
 for(size_t i=0;i<packed.size();i+=4){const uint32_t v=rng();std::memcpy(packed.data()+i,&v,std::min(size_t(4),packed.size()-i));}
 for(size_t i=0;i<packed.size();i+=packed_bytes){const uint16_t h=uint16_t(0x2000+(rng()&0x0fff));packed[i]=uint8_t(h);packed[i+1]=uint8_t(h>>8);}
 std::printf("preparing %zu packed bytes, %u experts, %u varied route cases\n",packed.size(),experts,cases);
 const auto cached=expand(packed.data(),packed.size(),columns);
 check_stop();
 std::vector<uint32_t> routes(size_t(cases)*slots);
 std::array<uint32_t,experts> pool{};std::iota(pool.begin(),pool.end(),0u);
 for(unsigned c=0;c<cases;++c){std::shuffle(pool.begin(),pool.end(),rng);std::copy_n(pool.begin(),slots,routes.begin()+c*slots);}
 std::vector<float> input(inputs),reference(outputs),candidate(outputs);
 for(auto& value:input)value=std::uniform_real_distribution<float>(-1,1)(rng);
 sycl::queue q(sycl::gpu_selector_v,[](sycl::exception_list es){for(const auto& e:es)std::rethrow_exception(e);},sycl::property::queue::in_order{});
 std::printf("device=%s cached_bytes=%u device_weight_bytes=%zu timing=host_batch_wait\n",q.get_device().get_info<sycl::info::device::name>().c_str(),cached_bytes,packed.size()+cached.size());
 auto* pw=sycl::malloc_device<uint8_t>(packed.size(),q);auto* cw=sycl::malloc_device<uint8_t>(cached.size(),q);
 auto* ids=sycl::malloc_device<uint32_t>(routes.size(),q);auto* x=sycl::malloc_device<float>(inputs,q);
 auto* py=sycl::malloc_device<float>(outputs,q);auto* cy=sycl::malloc_device<float>(outputs,q);
 if(!pw||!cw||!ids||!x||!py||!cy)throw std::runtime_error("device allocation failed");
 q.memcpy(pw,packed.data(),packed.size());q.memcpy(cw,cached.data(),cached.size());
 q.memcpy(ids,routes.data(),routes.size()*sizeof(uint32_t));q.memcpy(x,input.data(),inputs*sizeof(float));q.wait_and_throw();
 check_stop();
 auto batch=[&]<bool Cached>(unsigned start){
  for(unsigned n=0;n<cases;++n){const unsigned c=(start+n)%cases;
   submit<Cached>(q,Cached?cw:pw,ids+size_t(c)*slots,x+size_t(c)*slots*columns,(Cached?cy:py)+size_t(c)*slots*rows,rows,columns,slots);
  }
  q.wait_and_throw();
  check_stop(); // All submitted work has drained before cooperative exit.
 };
 // One comparison over all cases also warms both kernels and catches launch errors.
 batch.template operator()<false>(0);batch.template operator()<true>(0);
 q.memcpy(reference.data(),py,outputs*sizeof(float));q.memcpy(candidate.data(),cy,outputs*sizeof(float));q.wait_and_throw();
 for(size_t i=0;i<outputs;++i)if(std::bit_cast<uint32_t>(reference[i])!=std::bit_cast<uint32_t>(candidate[i])){
  std::printf("FAIL index=%zu packed=%08x cached=%08x\n",i,std::bit_cast<uint32_t>(reference[i]),std::bit_cast<uint32_t>(candidate[i]));return 2;
 }
 std::printf("PASS bitwise_outputs=%zu\n",outputs);
 std::array<double,samples> pt{},ct{};
 auto timed=[&]<bool Cached>(unsigned start){const auto t=std::chrono::steady_clock::now();batch.template operator()<Cached>(start);return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t).count()/cases;};
 for(unsigned s=0;s<samples;++s){const unsigned start=(s*11)%cases;
  if(s%2){ct[s]=timed.template operator()<true>(start);pt[s]=timed.template operator()<false>(start);}
  else{pt[s]=timed.template operator()<false>(start);ct[s]=timed.template operator()<true>(start);}
  std::printf("sample=%u packed_us=%.3f cached_us=%.3f\n",s,pt[s],ct[s]);
 }
 std::sort(pt.begin(),pt.end());std::sort(ct.begin(),ct.end());const double p=(pt[2]+pt[3])/2,c=(ct[2]+ct[3])/2;
 std::printf("RESULT packed_us=%.3f cached_us=%.3f kernel_speedup=%.4f target_pass_saving_ms=%.4f calls_per_pass=34 launches=%u\n",p,c,p/c,(p-c)*34/1000,cases*(2+2*samples));
 sycl::free(pw,q);sycl::free(cw,q);sycl::free(ids,q);sycl::free(x,q);sycl::free(py,q);sycl::free(cy,q);
 return 0;
} catch(const CooperativeStop&){std::fprintf(stderr,"STOP signal=%d or 60-second deadline; submitted batches drained\n",int(stop_requested));return 3;}
catch(const std::exception& e){std::fprintf(stderr,"ERROR %s\n",e.what());return 1;}
