// Lab bench (2026-10-26): kopt Multiply (BF16 weights, F32 activations/outputs, decode) vs dense_v2::bf16_rows.
#include <atomic>
#include "stage2/packet6-kopt/kernels.cpp"
#include "stage2/packet6-kopt/dense_v2.hpp"
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <algorithm>
#include <functional>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
using namespace iq3;
static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}
static sycl::event ref_gemv(sycl::queue&q,const uint16_t* W,const float* x,float* y,uint32_t rows,uint32_t k){
 kopt::Multiply op;op.subgroup=32;op.matrices=1;op.local_stride=16;
 kopt::Descriptor d{Type::BF16,Type::F32,Type::F32,rows,k,size_t(k)*2,0,(size_t(rows)+3)/4,1u,1u,rows,false,0,1,2,0,0,0,false};
 op.desc[0]=d;op.groups=d.groups;
 std::array<void*,3> p{(void*)W,(void*)x,(void*)y};return op.submit(q,std::span<void* const>(p.data(),3),{});
}
template<unsigned R,unsigned U> static sycl::event v2_gemv(sycl::queue&q,const uint16_t* W,const float* x,float* y,uint32_t rows,uint32_t k){
 const size_t sub=(rows+R-1)/R;const size_t wg=128;const size_t glob=(sub*32+wg-1)/wg*wg;const uint32_t rb=k*2;
 return q.parallel_for(sycl::nd_range<1>(glob,wg),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{kopt::dense_v2::bf16_rows<R,U>(reinterpret_cast<const uint8_t*>(W),x,y,rows,k,rb,it,uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(it.get_sub_group().get_group_linear_id()));});
}

#include <sycl/ext/oneapi/experimental/prefetch.hpp>
// Bench-only: bf16_rows R=1 with an L2/L1 prefetch of the weight chunk D chunks ahead (same arithmetic).
template<unsigned U,unsigned D,bool L1> static void bf16_pf(const uint8_t* W,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t rb,sycl::nd_item<1> it){
 namespace sx=sycl::ext::oneapi::experimental;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t row=uint32_t(it.get_group_linear_id())*uint32_t(it.get_local_range(0)/32)+uint32_t(sg.get_group_linear_id());if(row>=rows)return;
 const uint8_t* wr=W+size_t(row)*rb;float A=0.f;uint32_t base=lane*8u;
 for(;base+(U-1)*256u+8u<=k;base+=U*256u){
  if(base+D*256u+8u<=k){if constexpr(L1)sx::prefetch((void*)(wr+size_t(base+D*256u)*2u),16,sx::properties{sx::prefetch_hint_L1});else sx::prefetch((void*)(wr+size_t(base+D*256u)*2u),16,sx::properties{sx::prefetch_hint_L2});}
  sycl::vec<uint16_t,8> w[U];
  #pragma unroll
  for(unsigned u=0;u<U;++u)w[u]=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(wr+size_t(base+u*256u)*2u);
  #pragma unroll
  for(unsigned u=0;u<U;++u){const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x+base+u*256u);const auto a0=xv[0],a1=xv[1];
   #pragma unroll
   for(unsigned j=0;j<8;++j){const float xj=j<4?a0[j]:a1[j-4];const float product=kopt::dense_v2::bf16f(w[u][j])*xj;A=A+product;}}
 }
 for(;base+8u<=k;base+=256u){const sycl::vec<float,4>*xv=reinterpret_cast<const sycl::vec<float,4>*>(x+base);const auto a0=xv[0],a1=xv[1];const auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(wr+size_t(base)*2u);
  #pragma unroll
  for(unsigned j=0;j<8;++j){const float xj=j<4?a0[j]:a1[j-4];const float product=kopt::dense_v2::bf16f(w[j])*xj;A=A+product;}}
 if(base<k){const uint16_t* w16=reinterpret_cast<const uint16_t*>(wr);float values[8],wide[8];for(unsigned j=0;base+j<k;++j){values[j]=kopt::dense_v2::bf16f(w16[base+j]);wide[j]=x[base+j];}for(unsigned j=0;base+j<k;++j){const float product=values[j]*wide[j];A=A+product;}}
 for(unsigned lv=0;lv<5;++lv){const float o=sycl::permute_group_by_xor(sg,A,1u<<lv);A=((lane>>lv)&1u)?o+A:A+o;}
 if(lane==0)y[row]=A;
}
template<unsigned U,unsigned D,bool L1> static sycl::event pf_gemv(sycl::queue&q,const uint16_t* W,const float* x,float* y,uint32_t rows,uint32_t k){
 const size_t glob=(size_t(rows)*32+127)/128*128;const uint32_t rb=k*2;
 return q.parallel_for(sycl::nd_range<1>(glob,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{bf16_pf<U,D,L1>(reinterpret_cast<const uint8_t*>(W),x,y,rows,k,rb,it);});}
using Fn=std::function<sycl::event(sycl::queue&,const uint16_t*,const float*,float*,uint32_t,uint32_t)>;
int main(int argc,char**argv){
 const int iters=argc>1?std::atoi(argv[1]):30;const char* only=argc>2?argv[2]:nullptr;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 struct Shape{const char* name;uint32_t rows,k;};
 std::vector<Shape> shapes={{"hc.low",320,10240},{"hc.gate",10240,320},{"router",512,2560},{"qsa.iq",512,2560},{"gdn.a",96,2560},{"odd",37,2568},{"odd2",1000,1000}};
 std::vector<std::pair<const char*,Fn>> vars={{"ref",ref_gemv},
  {"v2_R1_U1",v2_gemv<1,1>},{"pf_U4_D8_L2",pf_gemv<4,8,false>},{"pf_U4_D16_L2",pf_gemv<4,16,false>},{"pf_U8_D16_L2",pf_gemv<8,16,false>},{"pf_U4_D8_L1",pf_gemv<4,8,true>},{"pf_U2_D12_L2",pf_gemv<2,12,false>},{"v2_R1_U4",v2_gemv<1,4>},{"v2_R1_U8",v2_gemv<1,8>},{"v2_R2_U4",v2_gemv<2,4>},{"v2_R4_U2",v2_gemv<4,2>},{"v2_R4_U4",v2_gemv<4,4>},
  {"v2_R8_U1",v2_gemv<8,1>},{"v2_R8_U2",v2_gemv<8,2>},{"v2_R16_U1",v2_gemv<16,1>},{"v2_R32_U1",v2_gemv<32,1>}};
 if(only){std::vector<std::pair<const char*,Fn>> k{vars[0]};for(size_t i=1;i<vars.size();++i)if(std::strstr(vars[i].first,only))k.push_back(vars[i]);vars=k;}
 const size_t FL=size_t(64)<<20;float* flush=sycl::malloc_device<float>(FL,q);q.memset(flush,0,FL*4).wait();
 std::mt19937 rng(5);int failures=0;
 for(auto sh:shapes){
  const size_t nw=size_t(sh.rows)*sh.k;std::vector<uint16_t> wh(nw);std::vector<float> xh(sh.k);std::normal_distribution<float> nd(0.f,1.f);
  for(auto&v:wh){float f=nd(rng)*0.05f;v=uint16_t(sycl::bit_cast<uint32_t>(f)>>16);}
  for(size_t i=0;i<xh.size();++i){xh[i]=nd(rng);if(i%61==0)xh[i]=0.f;if(i%67==0)xh[i]=-0.f;}
  for(size_t i=0;i<nw;i+=97)wh[i]=0x8000; // -0 weights
  uint16_t* W=sycl::malloc_device<uint16_t>(nw,q);float* x=sycl::malloc_device<float>(sh.k,q);float* yr=sycl::malloc_device<float>(sh.rows,q);float* yc=sycl::malloc_device<float>(sh.rows,q);
  q.memcpy(W,wh.data(),nw*2).wait();q.memcpy(x,xh.data(),sh.k*4).wait();
  q.memset(yr,0xff,sh.rows*4).wait();vars[0].second(q,W,x,yr,sh.rows,sh.k).wait();std::vector<uint32_t> r(sh.rows),c(sh.rows);q.memcpy(r.data(),yr,sh.rows*4).wait();
  for(size_t vi=0;vi<vars.size();++vi){auto&v=vars[vi];
   q.memset(yc,0xff,sh.rows*4).wait();v.second(q,W,x,yc,sh.rows,sh.k).wait();q.memcpy(c.data(),yc,sh.rows*4).wait();
   size_t diff=0;for(size_t i=0;i<sh.rows;++i)diff+=r[i]!=c[i];if(diff){++failures;std::printf("FAIL %s %s: %zu rows differ\n",sh.name,v.first,diff);}
   std::vector<double> th,tc;
   for(int i=0;i<iters+3;++i){auto e=v.second(q,W,x,yc,sh.rows,sh.k);double t=us(e);if(i>=3)th.push_back(t);}
   for(int i=0;i<iters+3;++i){q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int kk=0;kk<16;++kk)acc+=flush[b+kk];if(acc==12345.f)flush[0]=acc;});
    auto e=v.second(q,W,x,yc,sh.rows,sh.k);double t=us(e);if(i>=3)tc.push_back(t);}
   std::sort(th.begin(),th.end());std::sort(tc.begin(),tc.end());
   std::printf("timing %-8s rows %5u k %5u %-10s hot %7.2f cold %7.2f us  (cold GB/s %.0f)\n",sh.name,sh.rows,sh.k,v.first,th[th.size()/2],tc[tc.size()/2],nw*2/tc[tc.size()/2]/1e3);
  }
  sycl::free(W,q);sycl::free(x,q);sycl::free(yr,q);sycl::free(yc,q);
 }
 // fused pair: low (320 x 10240) + inject (4 x 10240) sharing x, two descriptors (generic_engine fused_gemv)
 {const uint32_t k=10240,r1=320,r2=4;std::normal_distribution<float> nd(0.f,1.f);
  std::vector<uint16_t> w1(size_t(r1)*k),w2(size_t(r2)*k);std::vector<float> xh(k);for(auto&v:w1)v=uint16_t(sycl::bit_cast<uint32_t>(nd(rng)*0.05f)>>16);for(auto&v:w2)v=uint16_t(sycl::bit_cast<uint32_t>(nd(rng)*0.05f)>>16);for(auto&v:xh)v=nd(rng);
  uint16_t* W1=sycl::malloc_device<uint16_t>(w1.size(),q);uint16_t* W2=sycl::malloc_device<uint16_t>(w2.size(),q);float* x=sycl::malloc_device<float>(k,q);
  float* y1r=sycl::malloc_device<float>(r1,q);float* y2r=sycl::malloc_device<float>(r2,q);float* y1c=sycl::malloc_device<float>(r1,q);float* y2c=sycl::malloc_device<float>(r2,q);
  q.memcpy(W1,w1.data(),w1.size()*2).wait();q.memcpy(W2,w2.data(),w2.size()*2).wait();q.memcpy(x,xh.data(),k*4).wait();
  kopt::Multiply op;op.subgroup=32;op.matrices=2;op.local_stride=16;
  op.desc[0]=kopt::Descriptor{Type::BF16,Type::F32,Type::F32,r1,k,size_t(k)*2,0,(size_t(r1)+3)/4,1u,1u,r1,false,0,1,2,0,0,0,false};
  op.desc[1]=kopt::Descriptor{Type::BF16,Type::F32,Type::F32,r2,k,size_t(k)*2,op.desc[0].groups,(size_t(r2)+3)/4,1u,1u,r2,false,3,1,4,0,0,0,false};
  op.groups=op.desc[0].groups+op.desc[1].groups;
  std::array<void*,5> p{(void*)W1,(void*)x,(void*)y1r,(void*)W2,(void*)y2r};op.submit(q,std::span<void* const>(p.data(),5),{}).wait();
  std::array<kopt::dense_v2::Mat,4> m{};m[0]={reinterpret_cast<const uint8_t*>(W1),x,y1c,r1,k,k*2,0};m[1]={reinterpret_cast<const uint8_t*>(W2),x,y2c,r2,k,k*2,r1};
  const size_t glob=(size_t(r1+r2)*32+127)/128*128;
  q.parallel_for(sycl::nd_range<1>(glob,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{kopt::dense_v2::bf16_multi<1,8>(m,2,it);}).wait();
  std::vector<uint32_t> a(r1),b(r1),c2(r2),d2(r2);q.memcpy(a.data(),y1r,r1*4).wait();q.memcpy(b.data(),y1c,r1*4).wait();q.memcpy(c2.data(),y2r,r2*4).wait();q.memcpy(d2.data(),y2c,r2*4).wait();
  size_t diff=0;for(uint32_t i=0;i<r1;++i)diff+=a[i]!=b[i];for(uint32_t i=0;i<r2;++i)diff+=c2[i]!=d2[i];
  if(diff){++failures;std::printf("FAIL fused pair: %zu outputs differ\n",diff);}else std::printf("fused pair exact (%u + %u rows)\n",r1,r2);}
 // streaming read bandwidth reference: 512 MB read of random data
 {const size_t N=size_t(128)<<20;float* big=sycl::malloc_device<float>(N,q);{std::vector<uint32_t> h(N/16);std::mt19937 g2(9);for(auto&v:h)v=g2();for(size_t o=0;o<N;o+=h.size())q.memcpy(big+o,h.data(),h.size()*4).wait();}float* out=sycl::malloc_device<float>(1,q);
  std::vector<double> t;for(int i=0;i<10;++i){auto e=q.parallel_for(sycl::nd_range<1>(N/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id();const sycl::vec<float,4>*p=reinterpret_cast<const sycl::vec<float,4>*>(big)+b*4;float acc=0.f;for(int kk=0;kk<4;++kk){auto v=p[kk];acc+=v[0]+v[1]+v[2]+v[3];}if(acc==12345.f)out[0]=acc;});t.push_back(us(e));}
  std::sort(t.begin(),t.end());std::printf("stream read 512 MB: %.1f us = %.0f GB/s (min %.0f GB/s)\n",t[t.size()/2],N*4/t[t.size()/2]/1e3,N*4/t[0]/1e3);}
 std::printf("exactness failures %d\n",failures);
 return failures?1:0;
}
