// Lab bench (2026-10-26): kopt Multiply (Q8_0 / Q6_K raw rows, F32 activations) vs dense_v2::quant_rows.
#include <atomic>
#include "stage2/packet6-kopt/kernels.cpp"
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <algorithm>
#include <functional>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
using namespace iq3;
static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}
template<Type T> static sycl::event ref_gemv(sycl::queue&q,const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k){
 kopt::Multiply op;op.subgroup=32;op.matrices=1;const size_t rb=size_t(k)/layout(T).elements*layout(T).bytes;op.local_stride=(rb+15)/16*16;
 kopt::Descriptor d{T,Type::F32,Type::F32,rows,k,rb,0,(size_t(rows)+3)/4,1u,1u,rows,false,0,1,2,0,0,0,false};op.desc[0]=d;op.groups=d.groups;
 std::array<void*,3> p{(void*)W,(void*)x,(void*)y};return op.submit(q,std::span<void* const>(p.data(),3),{});}
template<Type T,unsigned R> static sycl::event staged(sycl::queue&q,const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k){
 const uint32_t rb=k/layout(T).elements*layout(T).bytes;const size_t stride=(rb+15)/16*16;std::array<kopt::dense_v2::Mat,4> m{};m[0]={W,x,y,rows,k,rb,0};
 const size_t sub=(rows+R-1)/R,glob=(sub*32+127)/128*128;
 return q.submit([&](sycl::handler& h){sycl::local_accessor<uint8_t,1> st(stride*R*4,h);
  h.parallel_for(sycl::nd_range<1>(glob,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{kopt::quant_rows_staged<T,R>(m,1,stride,st.template get_multi_ptr<sycl::access::decorated::no>().get(),it);});});}
using Fn=std::function<sycl::event(sycl::queue&,const uint8_t*,const float*,float*,uint32_t,uint32_t)>;
int main(int argc,char**argv){
 const int iters=argc>1?std::atoi(argv[1]):20;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 struct Shape{const char* name;Type t;uint32_t rows,k;};
 std::vector<Shape> shapes={{"shexpdown",Type::Q8_0,2560,640},{"shexp.Q6_K",Type::Q6_K,640,2560},{"q8_odd",Type::Q8_0,37,2560},{"qsa.k",Type::Q6_K,512,2560},{"q6_odd",Type::Q6_K,1000,1536},{"q8_big",Type::Q8_0,2560,6144}};
 const size_t FL=size_t(64)<<20;float* flush=sycl::malloc_device<float>(FL,q);q.memset(flush,0,FL*4).wait();
 std::mt19937 rng(11);int failures=0;
 {float* wa=sycl::malloc_device<float>(1<<24,q);for(int i=0;i<300;++i)q.parallel_for(sycl::range<1>(1<<24),[=](sycl::id<1> i){wa[i]=wa[i]*0.5f+1.f;});q.wait();sycl::free(wa,q);}
 for(auto sh:shapes){
  const auto l=layout(sh.t);const size_t rb=sh.k/l.elements*l.bytes,nb=rb*sh.rows;std::vector<uint8_t> wh(nb);for(auto&b:wh)b=uint8_t(rng());
  // finite half scales: Q8_0 d at block offset 0, Q6_K d at 208
  for(size_t r=0;r<sh.rows;++r)for(size_t b=0;b<sh.k/l.elements;++b){uint8_t* blk=wh.data()+r*rb+b*l.bytes;const size_t at=sh.t==Type::Q6_K?208:0;float f=std::uniform_real_distribution<float>(-0.02f,0.02f)(rng);sycl::half h(f);uint16_t hb=sycl::bit_cast<uint16_t>(h);blk[at]=hb&255;blk[at+1]=hb>>8;}
  std::vector<float> xh(sh.k);std::normal_distribution<float> nd(0.f,1.f);for(size_t i=0;i<xh.size();++i){xh[i]=nd(rng);if(i%53==0)xh[i]=-0.f;}
  uint8_t* W=sycl::malloc_device<uint8_t>(nb+64,q);float* x=sycl::malloc_device<float>(sh.k,q);float* yr=sycl::malloc_device<float>(sh.rows,q);float* yc=sycl::malloc_device<float>(sh.rows,q);
  q.memcpy(W,wh.data(),nb).wait();q.memcpy(x,xh.data(),sh.k*4).wait();
  std::vector<std::pair<const char*,Fn>> vars;
  if(sh.t==Type::Q8_0)vars={{"ref",ref_gemv<Type::Q8_0>},{"st_R1",staged<Type::Q8_0,1>},{"st_R2",staged<Type::Q8_0,2>},{"st_R4",staged<Type::Q8_0,4>},{"st_R8",staged<Type::Q8_0,8>}};
  else vars={{"ref",ref_gemv<Type::Q6_K>},{"st_R1",staged<Type::Q6_K,1>},{"st_R2",staged<Type::Q6_K,2>},{"st_R4",staged<Type::Q6_K,4>}};
  q.memset(yr,0xff,sh.rows*4).wait();vars[0].second(q,W,x,yr,sh.rows,sh.k).wait();std::vector<uint32_t> r(sh.rows),c(sh.rows);q.memcpy(r.data(),yr,sh.rows*4).wait();
  for(auto&v:vars){q.memset(yc,0xff,sh.rows*4).wait();v.second(q,W,x,yc,sh.rows,sh.k).wait();q.memcpy(c.data(),yc,sh.rows*4).wait();
   size_t diff=0;for(size_t i=0;i<sh.rows;++i)diff+=r[i]!=c[i];if(diff){++failures;std::printf("FAIL %s %s %zu\n",sh.name,v.first,diff);}
   std::vector<double> th,tc;for(int i=0;i<iters+3;++i){double t=us(v.second(q,W,x,yc,sh.rows,sh.k));if(i>=3)th.push_back(t);}
   for(int i=0;i<iters+3;++i){q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int kk=0;kk<16;++kk)acc+=flush[b+kk];if(acc==12345.f)flush[0]=acc;});double t=us(v.second(q,W,x,yc,sh.rows,sh.k));if(i>=3)tc.push_back(t);}
   std::sort(th.begin(),th.end());std::sort(tc.begin(),tc.end());
   std::printf("timing %-10s rows %5u k %5u %-6s hot %7.2f cold %7.2f us (%.2f MB)\n",sh.name,sh.rows,sh.k,v.first,th[th.size()/2],tc[tc.size()/2],nb/1e6);}
  sycl::free(W,q);sycl::free(x,q);sycl::free(yr,q);sycl::free(yc,q);}
 std::printf("exactness failures %d\n",failures);return failures?1:0;}
