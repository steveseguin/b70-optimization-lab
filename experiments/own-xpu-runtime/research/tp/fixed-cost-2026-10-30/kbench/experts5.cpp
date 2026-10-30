// [fixed-cost-2026-10-30 lab copy of research/kbench/experts.cpp: 5-slot (four-card compact) arms]
// Routed expert GEMV structure study (IQ2_S gate/up shape: 640 rows x K=2560 per slot, F32 activations), bitwise
// against the engine's arithmetic (kopt decode8<IQ2_S>: lane l owns k=l*8+256*i, product then add, adjacent-pair tree).
// Questions, each format-independent:
//   1. codebook in local memory instead of a global constant gather;
//   2. gate+up in one launch (20 slots) instead of two launches of 10;
//   3. next-iteration byte loads issued before the current decode (software prefetch);
//   4. rows per subgroup and subgroups per work-group.
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
inline float half_scale(uint32_t h){return ((h>>10)&31)==31?half_sw(h):float(sycl::bit_cast<sycl::half>(uint16_t(h)));}
// The bytes one decode8 needs, fetched as raw values.
struct Raw{uint32_t d,qs,qh,signs,sc;};
inline Raw fetch(const uint8_t* row,size_t k){auto b=row+(k/256)*82;unsigned i=k%256,q=i/8;return Raw{u16(b),b[2+q],b[66+q/4],b[34+q],b[74+i/32]};}
// Instruction diet, every value bitwise unchanged: 32-bit index math, the 64-bit codebook word as two 32-bit halves,
// and the +-1 multiply as a sign-bit XOR (exact for every non-NaN; scale*grid is finite here).
template<int M,class Grid> inline void decode_lean(const Raw& r,unsigned i,const Grid& grid_of,float* v){
  unsigned q=i/8;unsigned ix=r.qs|(((r.qh>>(2*(q%4)))&3)<<8);uint64_t grid=grid_of(ix);const uint32_t lo=uint32_t(grid),hi=uint32_t(grid>>32);
  unsigned sc=(r.sc>>(4*((i/16)%2)))&15;float scale=(half_scale(r.d)*(0.5f+float(sc)))*0.25f;
  #pragma unroll
  for(unsigned j=0;j<8;++j){const uint32_t g=(M&2)?((j<4?lo:hi)>>(8*(j&3)))&255:uint32_t((grid>>(8*j))&255);const float m=scale*float(g);
    if constexpr((M&4)!=0)v[j]=sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(m)^(((r.signs>>j)&1u)<<31));else v[j]=m*float((r.signs>>j)&1?-1:1);}}
inline Raw fetch_lean(const uint8_t* row,unsigned k){const uint8_t* b=row+(k/256u)*82u;unsigned i=k%256u,q=i/8u;return Raw{u16(b),b[2+q],b[66+q/4],b[34+q],b[74+i/32]};}
template<class Grid> inline void decode(const Raw& r,size_t k,const Grid& grid_of,float* v){
  unsigned i=k%256,q=i/8;unsigned ix=r.qs|(((r.qh>>(2*(q%4)))&3)<<8);uint64_t grid=grid_of(ix);
  unsigned sc=(r.sc>>(4*((i/16)%2)))&15;float scale=(half_scale(r.d)*(0.5f+float(sc)))*0.25f;
  for(unsigned j=0;j<8;++j)v[j]=(scale*float((grid>>(8*j))&255))*float((r.signs>>j)&1?-1:1);}
constexpr int K=2560,ROWS=640,RB=K/256*82,GRID=1024;
template<int V> struct KK;
// SLOTS slots, R rows per subgroup, SGS subgroups per work-group, LOCAL: codebook in local memory, PF: prefetch.
template<int V,int SLOTS,int R,int SGS,bool LOCAL,bool PF,int DIET=0>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32;constexpr size_t blocks=ROWS/R,total=size_t(SLOTS)*blocks,groups=(total+SGS-1)/SGS;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<uint64_t,1> table(LOCAL?GRID:1,h);
    h.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
      auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
      if constexpr(LOCAL){for(unsigned i=it.get_local_linear_id();i<GRID;i+=SG*SGS)table[i]=iq3::iq2_s_grid[i];it.barrier(sycl::access::fence_space::local_space);}
      auto grid_of=[&](unsigned ix)->uint64_t{if constexpr(LOCAL)return table[ix];else return iq3::iq2_s_grid[ix];};
      const size_t logical=it.get_group_linear_id()*SGS+sg.get_group_linear_id();if(logical>=total)return;
      const size_t slot=logical/blocks,row0=(logical%blocks)*R;
      const uint8_t* base=w+(size_t(expert[slot])*ROWS+row0)*RB;const float* xs=x+size_t(slot%10)*K;
      float acc[R];for(int r=0;r<R;++r)acc[r]=0;
      Raw next[R];
      if constexpr(PF){
        #pragma unroll
        for(int r=0;r<R;++r)next[r]=fetch(base+size_t(r)*RB,size_t(lane)*8);}
      if constexpr(DIET){
        for(unsigned k=lane*8u;k<unsigned(K);k+=SG*8u){
          float in8[8];
          #pragma unroll
          for(int j=0;j<8;++j)in8[j]=xs[k+j];
          #pragma unroll
          for(int r=0;r<R;++r){const Raw raw=(DIET&1)?fetch_lean(base+unsigned(r)*unsigned(RB),k):fetch(base+size_t(r)*RB,size_t(k));float values[8];decode_lean<DIET>(raw,k%256u,grid_of,values);
            #pragma unroll
            for(int j=0;j<8;++j){float product=values[j]*in8[j];acc[r]=acc[r]+product;}}
        }
      } else
      for(size_t k=size_t(lane)*8;k<K;k+=SG*8){
        float in8[8];for(int j=0;j<8;++j)in8[j]=xs[k+j];
        Raw cur[R];
        #pragma unroll
        for(int r=0;r<R;++r){if constexpr(PF){cur[r]=next[r];if(k+SG*8<K)next[r]=fetch(base+size_t(r)*RB,k+SG*8);}else cur[r]=fetch(base+size_t(r)*RB,k);}
        #pragma unroll
        for(int r=0;r<R;++r){float values[8];decode(cur[r],k,grid_of,values);for(int j=0;j<8;++j){float product=values[j]*in8[j];acc[r]=acc[r]+product;}}
      }
      for(int r=0;r<R;++r){float a=acc[r];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
        if(lane==0)y[slot*ROWS+row0+r]=a;}});});
}
// Exact replica of the engine's MultiplyBlockRows<R> loop (runtime k, per-element bounds conditions, size_t math,
// kopt decode8<IQ2_S>), the true baseline.
inline void decode8_u32(const uint8_t* row,uint32_t k,float* v){
  const uint8_t* b=row+(k/256u)*82u;unsigned i=k%256u,q=i/8u;
  unsigned ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
  uint64_t grid=iq3::iq2_s_grid[ix];unsigned signs=b[34+q];
  unsigned sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
  float scale=(half_scale(u16(b))*(0.5f+float(sc)))*0.25f;
  #pragma unroll
  for(unsigned j=0;j<8;++j)v[j]=(scale*float(uint32_t((grid>>(8*j))&255)))*float((signs>>j)&1?-1:1);}
inline void decode8_engine(const uint8_t* row,size_t k,float* v){
  auto b=row+(k/256)*82;unsigned i=k%256,q=i/8;
  unsigned ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
  uint64_t grid=iq3::iq2_s_grid[ix];unsigned signs=b[34+q];
  unsigned sc=(b[74+i/32]>>(4*((i/16)%2)))&15;
  float scale=(half_scale(u16(b))*(0.5f+float(sc)))*0.25f;
  for(unsigned j=0;j<8;++j)v[j]=(scale*float((grid>>(8*j))&255))*float((signs>>j)&1?-1:1);}
template<int V,int SLOTS,unsigned R,int LEAN,uint32_t KC=0>
sycl::event engine(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y,size_t dk,size_t span,size_t rb){
  constexpr unsigned SG=32,Subgroups=4;const size_t blocks=(span+R-1)/R,total=blocks*SLOTS,groups=(total+Subgroups-1)/Subgroups;
  return q.submit([&](sycl::handler& h){h.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*Subgroups,SG*Subgroups),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
    const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
    const size_t slot=logical/blocks,first=(logical%blocks)*R;
    const float* xs=x+(slot%10)*dk;const uint8_t* wp=w;
    float acc[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i)acc[i]=0;
    if constexpr(LEAN==0){
    for(size_t k=size_t(lane)*8;k<dk;k+=size_t(SG)*8){
      float input[8];for(unsigned j=0;j<8 && k+j<dk;++j)input[j]=xs[k+j];
      #pragma unroll
      for(unsigned i=0;i<R;++i){const size_t row=first+i;if(row>=span)continue;
        const uint8_t* source=wp+(size_t(expert[slot])*span+row)*rb;float values[8];
        if(k+8<=dk)decode8_engine(source,k,values);
        for(unsigned j=0;j<8 && k+j<dk;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}}}
    } else if constexpr(LEAN==2){
    // Hoisted row pointers (expert id read once), 32-bit column index, fixed-trip unrolled full chunks.
    const uint8_t* rows[R];bool live[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){live[i]=first+i<span;rows[i]=wp+(size_t(expert[slot])*span+(live[i]?first+i:first))*rb;}
    const uint32_t k32=KC?KC:uint32_t(dk);uint32_t k=lane*8u;
    #pragma unroll 2
    for(;k+8u<=k32;k+=SG*8u){
      float input[8];
      #pragma unroll
      for(unsigned j=0;j<8;++j)input[j]=xs[k+j];
      #pragma unroll
      for(unsigned i=0;i<R;++i){if(KC==0&&!live[i])continue;float values[8];
        if constexpr(KC!=0){const Raw raw=fetch_lean(rows[i],k);decode_lean<1>(raw,k%256u,[](unsigned ix){return iq3::iq2_s_grid[ix];},values);}else decode8_u32(rows[i],k,values);
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}}
    }
    } else {
    // Same arithmetic: full 8-column chunks run a fixed-trip unrolled body; only a ragged tail keeps the checks.
    for(size_t k=size_t(lane)*8;k<dk;k+=size_t(SG)*8){
      if(k+8<=dk){
        float input[8];
        #pragma unroll
        for(unsigned j=0;j<8;++j)input[j]=xs[k+j];
        #pragma unroll
        for(unsigned i=0;i<R;++i){const size_t row=first+i;if(row>=span)continue;
          const uint8_t* source=wp+(size_t(expert[slot])*span+row)*rb;float values[8];decode8_engine(source,k,values);
          #pragma unroll
          for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}}
      }}
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
      const size_t row=first+i;if(lane==0&&row<span)y[slot*span+row]=sum;}});});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(9);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(int b=0;b<K/256;++b){uint8_t* p=&hw[r*RB+b*82];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(10*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);
  // slots 0-4: "gate" experts, slots 5-9: "up" experts (other experts of the same buffer); x per slot%10 as the engine
  std::vector<int> he{3,17,5,29,11,38,2,23,31,7, 14,26,9,33,0,21,36,12,19,27};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(20*ROWS,q);auto* e=sycl::malloc_device<int>(20,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),20*4).wait();
  std::vector<float> ref(20*ROWS),out(20*ROWS);engine<90,10,4,0>(q,w,e,x,y,K,ROWS,RB).wait();q.memcpy(ref.data(),y,10*ROWS*4).wait();
  auto us=[](const sycl::event& a,const sycl::event& b){return (b.get_profiling_info<sycl::info::event_profiling::command_end>()-a.get_profiling_info<sycl::info::event_profiling::command_start>())/1e3;};
  // cold weights (L2 flushed before each sample), median of 50; output rows compared with the 10-slot engine replica
  auto time=[&](auto fn,size_t slots,const char* label){for(int i=0;i<10;++i)fn().second.wait();std::vector<double> cold;
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.second.wait();cold.push_back(us(ev.first,ev.second));}
    std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,10*ROWS*4).wait();
    const double c=cold[cold.size()/2];
    std::printf("  %-58s %7.1f us  %s\n",label,c,std::memcmp(out.data(),ref.data(),slots*ROWS*4)?"DIFFERS":"bitwise-equal");};
  auto one=[&](auto f){return [=]{auto ev=f();return std::pair{ev,ev};};};
  std::printf("IQ2_S routed GEMV replica (engine loop, R rows per subgroup, 4 subgroups per work-group), 640 x 2560 per slot, cold\n");
  for(int rep=0;rep<2;++rep){
  time(one([&]{return engine<91,10,4,0>(q,w,e,x,y,K,ROWS,RB);}),10,"R4, 10 slots (one card)");
  time(one([&]{return engine<92,5,4,0>(q,w,e,x,y,K,ROWS,RB);}),5,"R4, 5 slots (four-card compact, one of gate/up)");
  time([&]{auto a=engine<93,5,4,0>(q,w,e,x,y,K,ROWS,RB);auto b=engine<93,5,4,0>(q,w,e+5,x+5*K,y+5*ROWS,K,ROWS,RB);return std::pair{a,b};},10,"R4, 5 + 5 slots in two launches (gate, up today)");
  time(one([&]{return engine<94,10,4,0>(q,w,e,x,y,K,ROWS,RB);}),10,"R4, 5 + 5 slots in ONE launch (paired)");
  time(one([&]{return engine<95,5,2,0>(q,w,e,x,y,K,ROWS,RB);}),5,"R2, 5 slots");
  time([&]{auto a=engine<96,5,2,0>(q,w,e,x,y,K,ROWS,RB);auto b=engine<96,5,2,0>(q,w,e+5,x+5*K,y+5*ROWS,K,ROWS,RB);return std::pair{a,b};},10,"R2, 5 + 5 slots in two launches");
  time(one([&]{return engine<97,5,1,0>(q,w,e,x,y,K,ROWS,RB);}),5,"R1, 5 slots");
  time(one([&]{return engine<98,10,2,0>(q,w,e,x,y,K,ROWS,RB);}),10,"R2, 5 + 5 slots in ONE launch");
  }
}
