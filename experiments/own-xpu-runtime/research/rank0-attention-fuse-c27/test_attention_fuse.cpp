// OpenCL CPU-device bitwise test for raw Q8 R1/U2 attention + F32 attn.combine; GPU access is blocked by nodri.so.
#include <sycl/sycl.hpp>
#include "stage2/packet10-kopt5/expanded.hpp"
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
#include <bit>
#include <cstdio>
#include <limits>
#include <random>
#include <vector>

static constexpr uint32_t rows=37,K=6144,rb=6528,erb=7296;

static std::vector<uint8_t> make_gguf(){
 std::mt19937 g(91827);std::vector<uint8_t> v(size_t(rows)*rb);
 for(uint32_t r=0;r<rows;++r)for(uint32_t b=0;b<K/32;++b){
  const size_t o=size_t(r)*rb+b*34;const float scale=((r+b)%2?-1.f:1.f)*(0.00025f+float((r*193+b*17)%500)*0.00001f);
  const uint16_t h=iq3::half_bits(scale);v[o]=uint8_t(h);v[o+1]=uint8_t(h>>8);
  for(uint32_t j=0;j<32;++j)v[o+2+j]=uint8_t(g());
 }
 return v;
}
static float ref_row(const uint8_t* w,const float* x){
 float s[32];
 for(unsigned lane=0;lane<32;++lane){float sum=0;
  for(unsigned tile=lane*8;tile<K;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/32)));
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(w[tile+j]));float product=value*x[tile+j];sum=sum+product;}}
  s[lane]=sum;
 }
 for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];
 return s[0];
}
static size_t run_case(sycl::queue& q,const uint8_t* raw,const float* x,const std::vector<float>& attention,
                       uint32_t active,uint32_t error,const std::vector<float>& inject){
 uint8_t* w=sycl::malloc_device<uint8_t>(size_t(rows)*rb,q);float* xd=sycl::malloc_device<float>(K,q);
 float* y=sycl::malloc_device<float>(rows+64,q);float* streams=sycl::malloc_device<float>(4*rows+64,q);
 float* inj=sycl::malloc_device<float>(4,q);uint32_t* a=sycl::malloc_device<uint32_t>(1,q);uint32_t* e=sycl::malloc_device<uint32_t>(1,q);
 q.memcpy(w,raw,size_t(rows)*rb).wait();q.memcpy(xd,x,K*4).wait();q.memcpy(inj,inject.data(),16).wait();q.memcpy(a,&active,4).wait();q.memcpy(e,&error,4).wait();
 std::vector<float> initial(4*rows+64);std::mt19937 g(771+active*3+error);std::uniform_real_distribution<float> u(-2.f,2.f);
 for(size_t i=0;i<4*rows;++i)initial[i]=u(g);for(size_t i=4*rows;i<initial.size();++i)initial[i]=-777.f;
 std::vector<float> sentinel(rows+64,-777.f);
 q.memcpy(streams,initial.data(),initial.size()*4).wait();q.memcpy(y,sentinel.data(),sentinel.size()*4).wait();
 q.submit([&](sycl::handler& h){
  sycl::local_accessor<float,1> factor(4,h);
  h.parallel_for(sycl::nd_range<1>((size_t(rows)*32+127)/128*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   const unsigned local=it.get_local_linear_id();const bool enabled=*a&&!sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*e).load();
   if(local<4&&enabled)factor[local]=2.f*ng::sigmoid(inj[local]/4.f);
   it.barrier(sycl::access::fence_space::local_space);
   p33::raw::AttentionEpilogue epilogue{streams};
   p33::raw::dense_rows<iq3::Type::Q8_0,K,1,2>(w,xd,y,rows,rb,rows,1,it,enabled?&epilogue:nullptr,factor.get_pointer());
  });
 }).wait();
 std::vector<float> got_y(rows+64),got_streams(4*rows+64);q.memcpy(got_y.data(),y,got_y.size()*4).wait();q.memcpy(got_streams.data(),streams,got_streams.size()*4).wait();
 auto expected=initial;const bool enabled=active&&!error;
 if(enabled)for(uint32_t s=0;s<4;++s){const float factor=2.f*ng::sigmoid(inject[s]/4.f);for(uint32_t r=0;r<rows;++r)expected[size_t(s)*rows+r]=initial[size_t(s)*rows+r]+attention[r]*factor;}
 size_t bad=0;
 for(size_t i=0;i<got_y.size();++i){const float want=i<rows?attention[i]:-777.f;bad+=std::bit_cast<uint32_t>(got_y[i])!=std::bit_cast<uint32_t>(want);bad+=!std::isfinite(got_y[i]);}
 for(size_t i=0;i<got_streams.size();++i){bad+=std::bit_cast<uint32_t>(got_streams[i])!=std::bit_cast<uint32_t>(expected[i]);bad+=!std::isfinite(got_streams[i]);}
 std::printf("active=%u error=%u inject=[%g,%g,%g,%g]: attention %u + streams/sentinels %zu, mismatches %zu\n",active,error,inject[0],inject[1],inject[2],inject[3],rows,got_streams.size(),bad);
 sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);sycl::free(streams,q);sycl::free(inj,q);sycl::free(a,q);sycl::free(e,q);return bad;
}
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 const auto gguf=make_gguf();const auto expanded=iq3::expanded::expand(iq3::Type::Q8_0,gguf.data(),gguf.size(),K);const auto raw=denseraw::repack(iq3::Type::Q8_0,gguf.data(),gguf.size(),K);
 size_t bad=denseraw::check_rows(iq3::Type::Q8_0,raw.data(),expanded.data(),rows,K,erb);
 std::mt19937 g(551);std::uniform_real_distribution<float> u(-1.f,1.f);std::vector<float>x(K);for(auto& v:x)v=u(g);
 std::vector<float>attention(rows);for(uint32_t r=0;r<rows;++r)attention[r]=ref_row(expanded.data()+size_t(r)*erb,x.data());
 const float M=std::numeric_limits<float>::max();
 bad+=run_case(q,raw.data(),x.data(),attention,1,0,{-M,-0.25f,0.125f,M});
 bad+=run_case(q,raw.data(),x.data(),attention,0,0,{-4.f,-2.f,2.f,4.f});
 bad+=run_case(q,raw.data(),x.data(),attention,1,1,{-4.f,-2.f,2.f,4.f});
 bad+=run_case(q,raw.data(),x.data(),attention,0,1,{-4.f,-2.f,2.f,4.f});
 std::printf("%s\n",bad?"FAILED":"ALL PASSED");return bad?1:0;
}
