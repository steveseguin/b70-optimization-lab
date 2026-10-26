// Lab bench (2026-10-26): denseblock decode GEMV (Q4_K=12, Q5_K=13, IQ4_XS=23; F32 activations) timing + candidates.
#include <atomic>
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet194-expert-diet-engine/p33_submit.hpp"
#include "stage2/packet194-expert-diet-engine/performance.hpp"
#include "stage2/packet194-expert-diet-engine/adapter.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#define GSQN_RUNTIME_HEADERS_PROVIDED
#include "gsq-rco-iq3s/integration/build/private/additive/packed.hpp"
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/block.hpp"
#if __has_include("gsq-rco-iq3s/dense-packed-block/engine/build/source/block_v2.hpp")
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/block_v2.hpp"
#define HAVE_V2 1
#endif
#include <cstdio>
#include <random>
#include <vector>
#include <algorithm>
#include <functional>
#include <cstring>
#include <string>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}
template<unsigned T> static sycl::event ref(sycl::queue&q,const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k,size_t rb){
 denseblock::DenseBlockOperation<T,true> op;op.s=gsqn::Shape{rows,k,rb,1,1,false,false,true,false};
 std::array<void*,5> p{(void*)W,(void*)x,(void*)y,(void*)x,(void*)y};return op.submit(q,std::span<void* const>(p.data(),5),{});}
using Fn=std::function<sycl::event(sycl::queue&,const uint8_t*,const float*,float*,uint32_t,uint32_t,size_t)>;
int main(int argc,char**argv){
 const int iters=argc>1?std::atoi(argv[1]):20;const char* only=argc>2?argv[2]:nullptr;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 struct Shape{const char* name;unsigned t;uint32_t rows,k;};
 std::vector<Shape> shapes={{"qkv.Q5_K",13,10240,2560},{"qkv.IQ4_XS",23,10240,2560},{"z.Q4_K",12,6144,2560},{"z.Q5_K",13,6144,2560},{"shexp.Q4_K",12,640,2560},{"shexp.IQ4_XS",23,640,2560}};
 const size_t FL=size_t(64)<<20;float* flush=sycl::malloc_device<float>(FL,q);q.memset(flush,0,FL*4).wait();
 std::mt19937 rng(21);int failures=0;
 {float* wa=sycl::malloc_device<float>(1<<24,q);for(int i=0;i<300;++i)q.parallel_for(sycl::range<1>(1<<24),[=](sycl::id<1> i){wa[i]=wa[i]*0.5f+1.f;});q.wait();sycl::free(wa,q);} // warm-up
 for(auto sh:shapes){
  const size_t bb=sh.t==12?144:sh.t==13?176:136,rb=sh.k/256*bb,nb=rb*sh.rows;std::vector<uint8_t> wh(nb);for(auto&b:wh)b=uint8_t(rng());
  for(size_t r=0;r<sh.rows;++r)for(size_t b=0;b<sh.k/256;++b){uint8_t* blk=wh.data()+r*rb+b*bb;for(int h=0;h<(sh.t==23?1:2);++h){float f=std::uniform_real_distribution<float>(-0.01f,0.01f)(rng);uint16_t hb=sycl::bit_cast<uint16_t>(sycl::half(f));blk[2*h]=hb&255;blk[2*h+1]=hb>>8;}}
  std::vector<float> xh(sh.k);std::normal_distribution<float> nd(0.f,1.f);for(size_t i=0;i<xh.size();++i){xh[i]=nd(rng);if(i%71==0)xh[i]=-0.f;}
  uint8_t* W=sycl::malloc_device<uint8_t>(nb,q);float* x=sycl::malloc_device<float>(sh.k,q);float* yr=sycl::malloc_device<float>(sh.rows,q);float* yc=sycl::malloc_device<float>(sh.rows,q);
  q.memcpy(W,wh.data(),nb).wait();q.memcpy(x,xh.data(),sh.k*4).wait();
  std::vector<std::pair<const char*,Fn>> vars;
  if(sh.t==12)vars.push_back({"ref",ref<12>});if(sh.t==13)vars.push_back({"ref",ref<13>});if(sh.t==23)vars.push_back({"ref",ref<23>});
#ifdef HAVE_V2
#include "bench_block_variants.inc"
#endif
  q.memset(yr,0xff,sh.rows*4).wait();vars[0].second(q,W,x,yr,sh.rows,sh.k,rb).wait();std::vector<uint32_t> r(sh.rows),c(sh.rows);q.memcpy(r.data(),yr,sh.rows*4).wait();
  for(auto&v:vars){if(only&&v.first!=std::string("ref")&&!std::strstr(v.first,only))continue;
   q.memset(yc,0xff,sh.rows*4).wait();v.second(q,W,x,yc,sh.rows,sh.k,rb).wait();q.memcpy(c.data(),yc,sh.rows*4).wait();
   size_t diff=0;for(size_t i=0;i<sh.rows;++i)diff+=r[i]!=c[i];if(diff){++failures;std::printf("FAIL %s %s %zu\n",sh.name,v.first,diff);}
   std::vector<double> th,tc;for(int i=0;i<iters+3;++i){double t=us(v.second(q,W,x,yc,sh.rows,sh.k,rb));if(i>=3)th.push_back(t);}
   for(int i=0;i<iters+3;++i){q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int kk=0;kk<16;++kk)acc+=flush[b+kk];if(acc==12345.f)flush[0]=acc;});double t=us(v.second(q,W,x,yc,sh.rows,sh.k,rb));if(i>=3)tc.push_back(t);}
   std::sort(th.begin(),th.end());std::sort(tc.begin(),tc.end());
   std::printf("timing %-12s rows %5u %-10s hot %7.2f cold %7.2f us (%.2f MB, floor %.1f us)\n",sh.name,sh.rows,v.first,th[th.size()/2],tc[tc.size()/2],nb/1e6,nb/600e3);}
  sycl::free(W,q);sycl::free(x,q);sycl::free(yr,q);sycl::free(yc,q);}
 std::printf("exactness failures %d\n",failures);return failures?1:0;}
