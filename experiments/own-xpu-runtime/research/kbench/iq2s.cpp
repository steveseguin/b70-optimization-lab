// IQ2_S routed expert gate GEMV microbenchmark (10 slots x 640 rows x K=2560, F32 activations), bitwise against the
// engine's decode (kopt decode8<IQ2_S>, lane l owns k=l*8+256*i, product then add, adjacent-pair tree).
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#define KERNEL_GUARD_SKIP
#include "stage2/packet2/kernels/grids.hpp"
inline uint32_t u16(const uint8_t* b){return uint32_t(b[0])|uint32_t(b[1])<<8;}
inline float bits_float(uint32_t b){return sycl::bit_cast<float>(b);}
inline float half_sw(uint32_t h){uint32_t sign=(h&0x8000)<<16,e=(h>>10)&31,m=h&1023;
  if(e==31)return bits_float(sign|0x7f800000|(m?0x400000:0));if(e)return bits_float(sign|((e+112)<<23)|(m<<13));if(!m)return bits_float(sign);
  int exponent=-14;while(!(m&1024)){m<<=1;--exponent;}return bits_float(sign|(uint32_t(exponent+127)<<23)|((m&1023)<<13));}
template<int HW> inline void decode8(const uint8_t* row,size_t k,float* v){
  auto b=row+(k/256)*82;unsigned i=k%256,q=i/8;
  unsigned ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);uint64_t grid=iq3::iq2_s_grid[ix];unsigned signs=b[34+q];
  unsigned sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
  float h;const uint32_t hb=u16(b);if constexpr(HW==1)h=float(sycl::bit_cast<sycl::half>(uint16_t(hb)));else if constexpr(HW==2)h=((hb>>10)&31)==31?half_sw(hb):float(sycl::bit_cast<sycl::half>(uint16_t(hb)));else h=half_sw(hb);
  float scale=(h*(0.5f+float(sc)))*0.25f;
  for(unsigned j=0;j<8;++j)v[j]=(scale*float((grid>>(8*j))&255))*float((signs>>j)&1?-1:1);}
template<unsigned SG> inline void stage_row(const uint8_t* src,uint8_t* dst,size_t n,unsigned lane){
  size_t prefix=(16-(reinterpret_cast<uintptr_t>(src)&15))&15;prefix=prefix<n?prefix:n;
  for(size_t i=lane;i<prefix;i+=SG)dst[i]=src[i];size_t vectors=(n-prefix)/16;auto aligned=reinterpret_cast<const sycl::vec<uint32_t,4>*>(src+prefix);
  for(size_t j=lane;j<vectors;j+=SG){auto bytes=aligned[j].template as<sycl::vec<uint8_t,16>>();for(unsigned i=0;i<16;++i)dst[prefix+j*16+i]=bytes[i];}
  for(size_t i=prefix+vectors*16+lane;i<n;i+=SG)dst[i]=src[i];}
constexpr int K=2560,ROWS=640,SLOTS=10,RB=K/256*82;
template<int V> struct KK;
template<int V,int SGS,bool STAGE,int RowsPerSg,int HW>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32;const size_t total=size_t(SLOTS)*ROWS/RowsPerSg,groups=(total+SGS-1)/SGS;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<uint8_t,1> storage(STAGE?SGS*832:1,h);
    h.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
      auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id();
      const size_t logical=it.get_group_linear_id()*SGS+sub;const bool in=logical<total;
      const size_t slot=logical/(ROWS/RowsPerSg),row0=(logical%(ROWS/RowsPerSg))*RowsPerSg;
      const uint8_t* base=w+(size_t(in?expert[slot]:0)*ROWS+row0)*RB;const uint8_t* rowp=base;
      if constexpr(STAGE){auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+sub*832;if(in)stage_row<SG>(base,local,RB,lane);it.barrier(sycl::access::fence_space::local_space);rowp=local;}
      float acc[RowsPerSg];for(int r=0;r<RowsPerSg;++r)acc[r]=0;
      if(in)for(size_t k=size_t(lane)*8;k<K;k+=SG*8){float in8[8];for(int j=0;j<8;++j)in8[j]=x[slot*K+k+j];
        #pragma unroll
        for(int r=0;r<RowsPerSg;++r){float values[8];decode8<HW>(rowp+(STAGE?0:size_t(r)*RB),k,values);for(int j=0;j<8;++j){float product=values[j]*in8[j];acc[r]=acc[r]+product;}}}
      for(int r=0;r<RowsPerSg;++r){float a=acc[r];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
        if(lane==0&&in)y[slot*ROWS+row0+r]=a;}});});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(9);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(int b=0;b<K/256;++b){uint8_t* p=&hw[r*RB+b*82];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);run<0,4,true,1,0>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> cold;
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-44s cold %7.1f us  %s\n",label,cold[cold.size()/2],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("IQ2_S gate, 10 slots x 640 x 2560 (%.1f MB)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,4,true,1,0>(q,w,e,x,y);},"v0 staged SLM, 1 row/sg (original)");
  time([&]{return run<1,4,false,4,0>(q,w,e,x,y);},"v1 global, 4 rows/sg (engine now)");
  time([&]{return run<2,4,false,1,0>(q,w,e,x,y);},"v2 global, 1 row/sg");
  time([&]{return run<3,4,false,2,0>(q,w,e,x,y);},"v3 global, 2 rows/sg");
  time([&]{return run<4,4,false,4,1>(q,w,e,x,y);},"v4 global, 4 rows/sg, hw half");
  time([&]{return run<5,8,false,4,0>(q,w,e,x,y);},"v5 global, 4 rows/sg, 8 sg/wg");
  time([&]{return run<6,4,false,1,2>(q,w,e,x,y);},"v6 global, 1 row/sg, hw half (NaN-safe)");
  time([&]{return run<7,4,false,2,2>(q,w,e,x,y);},"v7 global, 2 rows/sg, hw half (NaN-safe)");
  time([&]{return run<8,4,false,4,2>(q,w,e,x,y);},"v8 global, 4 rows/sg, hw half (NaN-safe)");
}
