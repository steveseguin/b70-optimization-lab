// IQ3_XXS routed expert gate GEMV microbenchmark (iq3block::BlockOperation, 10 slots x 640 rows x K=2560, F32 x),
// bitwise against the engine's block_lane_sum: lane l owns k=256*block+32*group+l, product then add, adjacent tree.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <bit>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet2/kernels/grids.hpp"
inline uint32_t u16(const uint8_t* b){return uint32_t(b[0])|uint32_t(b[1])<<8;}
inline uint32_t u32(const uint8_t* b){return u16(b)|u16(b+2)<<16;}
inline float bits_float(uint32_t b){return sycl::bit_cast<float>(b);}
inline float half_sw(uint32_t h){uint32_t sign=(h&0x8000)<<16,e=(h>>10)&31,m=h&1023;
  if(e==31)return bits_float(sign|0x7f800000|(m?0x400000:0));if(e)return bits_float(sign|((e+112)<<23)|(m<<13));if(!m)return bits_float(sign);
  int exponent=-14;while(!(m&1024)){m<<=1;--exponent;}return bits_float(sign|(uint32_t(exponent+127)<<23)|((m&1023)<<13));}
template<bool HW> inline float halfv(uint32_t h){if constexpr(HW){if(((h>>10)&31)!=31)return float(sycl::bit_cast<sycl::half>(uint16_t(h)));}return half_sw(h);}
template<bool WORDS> inline float block_element(const uint8_t* b,float d,unsigned group,unsigned lane){
  uint32_t word;if constexpr(WORDS){auto p=reinterpret_cast<const uint16_t*>(b+66+4*group);word=uint32_t(p[0])|uint32_t(p[1])<<16;}else word=u32(b+66+4*group);
  const uint32_t code=(word>>(7*(lane/8)))&127;const uint32_t mask=code|((uint32_t(std::popcount(code))%2)<<7);const int sign=(mask>>(lane%8))&1?-1:1;
  const uint32_t mag=(iq3::iq3_grid[b[2+group*8+lane/4]]>>(8*(lane%4)))&255;
  return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);}
constexpr int K=2560,ROWS=640,SLOTS=10,RB=K/256*98;
template<int V> struct KK;
template<int V,int RowsPerSg,bool HW,bool WORDS>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32;const size_t total=size_t(SLOTS)*ROWS/RowsPerSg;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(total*SG,SG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
    const size_t slot=logical/(ROWS/RowsPerSg),row0=(logical%(ROWS/RowsPerSg))*RowsPerSg;
    float acc[RowsPerSg];for(int r=0;r<RowsPerSg;++r)acc[r]=0;
    for(int block=0;block<K/256;++block){
      #pragma unroll
      for(int r=0;r<RowsPerSg;++r){const uint8_t* packed=w+(size_t(expert[slot])*ROWS+row0+r)*RB+block*98;const float d=halfv<HW>(u16(packed));
        for(unsigned group=0;group<8;++group){const size_t k=block*256+group*32+lane;const float weight=block_element<WORDS>(packed,d,group,lane);const float product=weight*x[slot*K+k];acc[r]=acc[r]+product;}}
    }
    for(int r=0;r<RowsPerSg;++r){float a=acc[r];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
      if(lane==0)y[slot*ROWS+row0+r]=a;}});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(11);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(int b=0;b<K/256;++b){uint8_t* p=&hw[r*RB+b*98];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);run<0,1,false,false>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> cold;
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-40s cold %7.1f us  %s\n",label,cold[cold.size()/2],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("IQ3_XXS gate, 10 slots x 640 x 2560 (%.1f MB)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,1,false,false>(q,w,e,x,y);},"v0 engine block kernel");
  time([&]{return run<1,1,true,false>(q,w,e,x,y);},"v1 hw half (NaN-safe)");
  time([&]{return run<2,1,true,true>(q,w,e,x,y);},"v2 hw half + 16-bit word loads");
  time([&]{return run<3,2,true,true>(q,w,e,x,y);},"v3 v2 + 2 rows/sg");
  time([&]{return run<4,4,true,true>(q,w,e,x,y);},"v4 v2 + 4 rows/sg");
}
