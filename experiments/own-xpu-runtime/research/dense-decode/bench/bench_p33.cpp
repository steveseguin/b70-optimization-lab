// Lab bench (2026-10-26): p33.dense.segment decode (expanded Q6_K/Q8_0, F32) reference vs p33::v2::dense_rows.
#include <atomic>
#include "stage2/packet194-expert-diet-engine/p33_dense_v2.hpp"
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <algorithm>
#include <functional>
#include <string>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}
using T_=iq3::Type;
// Verbatim decode body of p33 Kernel<0,T,K,1,true> for a dense matrix (slot 0, no routes): one 32-lane group per row.
template<T_ T,unsigned K> static sycl::event ref(sycl::queue&q,const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t rb){
 return q.parallel_for(sycl::nd_range<1>(size_t(rows)*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
  auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),row=unsigned(it.get_group_linear_id());
  float sum=p33::dense_lane<T,K,true>(W+size_t(row)*rb,reinterpret_cast<const uint16_t*>(x),0,K,lane);
  for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
  if(lane==0)y[row]=sum;});}
template<T_ T,unsigned K,unsigned R,unsigned U> static sycl::event v2(sycl::queue&q,const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t rb){
 const size_t sub=(rows+R-1)/R,glob=(sub*32+127)/128*128;
 return q.parallel_for(sycl::nd_range<1>(glob,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{p33::v2::dense_rows<T,K,R,U>(W,x,y,rows,rb,it);});}
using Fn=std::function<sycl::event(sycl::queue&,const uint8_t*,const float*,float*,uint32_t,uint32_t)>;
int main(int argc,char**argv){
 const int iters=argc>1?std::atoi(argv[1]):20;const char* only=argc>2?argv[2]:nullptr;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 {float* wa=sycl::malloc_device<float>(1<<24,q);for(int i=0;i<300;++i)q.parallel_for(sycl::range<1>(1<<24),[=](sycl::id<1> i){wa[i]=wa[i]*0.5f+1.f;});q.wait();sycl::free(wa,q);}
 struct Shape{const char* name;T_ t;uint32_t rows,k;std::vector<std::pair<const char*,Fn>> vars;};
#define VARS(T,K) {{"ref",ref<T,K>},{"v2_R1_U1",v2<T,K,1,1>},{"v2_R1_U2",v2<T,K,1,2>},{"v2_R1_U4",v2<T,K,1,4>},{"v2_R2_U2",v2<T,K,2,2>},{"v2_R4_U1",v2<T,K,4,1>}}
 std::vector<Shape> shapes={{"attn.Q8_0",T_::Q8_0,2560,6144,VARS(T_::Q8_0,6144)},{"qkv.Q6_K",T_::Q6_K,10240,2560,VARS(T_::Q6_K,2560)},{"z.Q6_K",T_::Q6_K,6144,2560,VARS(T_::Q6_K,2560)},
  {"qgate.Q6_K",T_::Q6_K,12288,2560,VARS(T_::Q6_K,2560)},{"logits.Q6_K",T_::Q6_K,248320,2560,VARS(T_::Q6_K,2560)}};
 const size_t FL=size_t(64)<<20;float* flush=sycl::malloc_device<float>(FL,q);q.memset(flush,0,FL*4).wait();
 std::mt19937 rng(31);int failures=0;
 for(auto& sh:shapes){
  const uint32_t rb=uint32_t(iq3::expanded::row_bytes(sh.t,sh.k));const unsigned group=sh.t==T_::Q6_K?16:32;const size_t nb=size_t(rb)*sh.rows;
  std::vector<uint8_t> wh(nb);for(auto&b:wh)b=uint8_t(rng());
  for(size_t r=0;r<sh.rows;++r)for(unsigned g=0;g<sh.k/group;++g){float s=std::uniform_real_distribution<float>(-0.01f,0.01f)(rng);if(g%37==0)s=-0.f;uint32_t b=sycl::bit_cast<uint32_t>(s);std::memcpy(wh.data()+r*rb+sh.k+4*g,&b,4);}
  std::vector<float> xh(sh.k);std::normal_distribution<float> nd(0.f,1.f);for(size_t i=0;i<xh.size();++i){xh[i]=nd(rng);if(i%41==0)xh[i]=-0.f;}
  uint8_t* W=sycl::malloc_device<uint8_t>(nb,q);float* x=sycl::malloc_device<float>(sh.k,q);float* yr=sycl::malloc_device<float>(sh.rows,q);float* yc=sycl::malloc_device<float>(sh.rows,q);
  q.memcpy(W,wh.data(),nb).wait();q.memcpy(x,xh.data(),sh.k*4).wait();
  q.memset(yr,0xff,sh.rows*4).wait();sh.vars[0].second(q,W,x,yr,sh.rows,rb).wait();std::vector<uint32_t> r(sh.rows),c(sh.rows);q.memcpy(r.data(),yr,sh.rows*4).wait();
  for(auto&v:sh.vars){if(only&&std::string(v.first)!="ref"&&!std::strstr(v.first,only))continue;
   q.memset(yc,0xff,sh.rows*4).wait();v.second(q,W,x,yc,sh.rows,rb).wait();q.memcpy(c.data(),yc,sh.rows*4).wait();
   size_t diff=0;for(size_t i=0;i<sh.rows;++i)diff+=r[i]!=c[i];if(diff){++failures;std::printf("FAIL %s %s %zu\n",sh.name,v.first,diff);}
   std::vector<double> th,tc;const int it2=sh.rows>100000?5:iters;for(int i=0;i<it2+2;++i){double t=us(v.second(q,W,x,yc,sh.rows,rb));if(i>=2)th.push_back(t);}
   for(int i=0;i<it2+2;++i){q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int kk=0;kk<16;++kk)acc+=flush[b+kk];if(acc==12345.f)flush[0]=acc;});double t=us(v.second(q,W,x,yc,sh.rows,rb));if(i>=2)tc.push_back(t);}
   std::sort(th.begin(),th.end());std::sort(tc.begin(),tc.end());const double read=double(sh.rows)*(sh.k+4*sh.k/group);
   std::printf("timing %-12s rows %6u %-9s hot %8.2f cold %8.2f us (reads %.1f MB, floor %.1f us)\n",sh.name,sh.rows,v.first,th[th.size()/2],tc[tc.size()/2],read/1e6,read/600e3);}
  sycl::free(W,q);sycl::free(x,q);sycl::free(yr,q);sycl::free(yc,q);}
 std::printf("exactness failures %d\n",failures);return failures?1:0;}
