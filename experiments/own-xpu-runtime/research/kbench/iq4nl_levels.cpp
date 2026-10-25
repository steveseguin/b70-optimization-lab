// IQ4_NL routed expert down (10 slots x 2560 rows x K=640, F32 activations, 2 rows per subgroup), bitwise against the
// engine's own code: this file includes the engine's kopt reference.hpp, so the baseline decode8<IQ4_NL> is the
// production decoder, in the production lean loop (MultiplyBlockRows). Variant: the 16 levels as floats held by lanes
// 0..15 and fetched with one subgroup shuffle per weight instead of iq4_level's select chain and int conversion
// (float(int(level)) is the same float either way).
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#define KERNEL_GUARD_SKIP
#include "stage2/packet6-kopt/reference.hpp"
using iq3::Type;
constexpr unsigned K=640,ROWS=2560,SLOTS=10,RB=K/32*18,R=2,SG=32;
template<int V> struct KK;
// SHUFFLE=false: production decode8<IQ4_NL>. SHUFFLE=true: same word reads and scale, level by shuffle.
template<int V,bool SHUFFLE>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr size_t blocks=ROWS/R,total=size_t(SLOTS)*blocks,groups=(total+3)/4;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*4,SG*4),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
    const size_t logical=it.get_group_linear_id()*4+sg.get_group_linear_id();if(logical>=total)return;
    const size_t slot=logical/blocks,first=(logical%blocks)*R;
    const float* xs=x+slot*K;const uint8_t* rows[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i)rows[i]=w+(size_t(expert[slot])*ROWS+first+i)*RB;
    const float level=float(iq3::iq4_level(lane&15));
    float acc[R]{};
    for(uint32_t k=lane*8u;k+8u<=K;k+=SG*8u){
      float input[8];
      #pragma unroll
      for(unsigned j=0;j<8;++j)input[j]=xs[k+j];
      #pragma unroll
      for(unsigned i=0;i<R;++i){
        float values[8];
        if constexpr(!SHUFFLE)iq3::kopt::decode8<Type::IQ4_NL>(rows[i],k,values);
        else {
          const uint8_t* b=rows[i]+(k/32)*18;const unsigned e=k%32;const float scale=iq3::kopt::half_scale(iq3::u16(b));
          const uint8_t* qp=b+2+(e&15);const uintptr_t at=reinterpret_cast<uintptr_t>(qp);uint32_t lo,hi;
          if((at&3)==0){lo=*reinterpret_cast<const uint32_t*>(qp);hi=*reinterpret_cast<const uint32_t*>(qp+4);}
          else {const uint32_t* wd=reinterpret_cast<const uint32_t*>(qp-2);lo=(wd[0]>>16)|(wd[1]<<16);hi=(wd[1]>>16)|(uint32_t(*reinterpret_cast<const uint16_t*>(qp+6))<<16);}
          const unsigned shift=(e/16)*4;
          #pragma unroll
          for(unsigned j=0;j<8;++j){const unsigned n=((((j<4?lo:hi)>>(8*(j&3)))&255)>>shift)&15;values[j]=scale*sycl::select_from_group(sg,level,n);}
        }
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
      }
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[slot*ROWS+first+i]=sum;}
  });
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(7);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/32;++b){uint8_t* p=&hw[r*RB+b*18];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);run<0,false>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> warm,cold;
    for(int i=0;i<100;++i){auto ev=fn();ev.wait();warm.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(warm.begin(),warm.end());std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-40s warm %7.1f us  cold %7.1f us  %s\n",label,warm[50],cold[25],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("IQ4_NL down, 10 x 2560 x 640, 2 rows/subgroup (%.1f MB)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,false>(q,w,e,x,y);},"production decode8 (warm-up)");
  time([&]{return run<0,false>(q,w,e,x,y);},"production decode8");
  time([&]{return run<1,true>(q,w,e,x,y);},"levels by subgroup shuffle");
}
