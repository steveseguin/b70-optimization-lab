// IQ3_XXS routed expert gate (10 slots x 640 rows x K=2560, F32 activations), 4 rows per subgroup: an exact replica of
// the engine's lean BlockRowsOperation<4> loop (k = block*256 + group*32 + lane, block_element_words, product then add,
// adjacent-pair tree) and exact decoder variants. All must be bitwise equal to the replica.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#define KERNEL_GUARD_SKIP
#include "stage2/packet2/kernels/grids.hpp"
#include "stage2/packet2/kernels/math.hpp"
constexpr unsigned K=2560,ROWS=640,SLOTS=10,RB=K/256*98,R=4;
// Engine: block_element_words (two 16-bit reads of the scale/sign word, one byte read and a grid gather per element).
inline float element_engine(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const auto mag=(iq3::iq3_grid[b[2+group*8+lane/4]]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
// Variant: the same value, with the +-1 multiply as a sign-bit XOR (exact: the product before it is finite) and the
// grid index byte taken from two 16-bit words of the group's 8 index bytes.
template<bool XOR,bool WORDS> inline float element_variant(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const uint32_t mask=code|((std::popcount(code)%2)<<7);
 uint32_t index;
 if constexpr(WORDS){const auto*q=reinterpret_cast<const uint16_t*>(b+2+group*8);const uint32_t pair=q[lane/8];index=(pair>>(8*((lane/4)%2)))&255;}
 else index=b[2+group*8+lane/4];
 const uint32_t mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 const float m=((d*(0.5f+float(word>>28)))*0.5f)*float(mag);
 if constexpr(XOR)return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(m)^(((mask>>(lane%8))&1u)<<31));
 else return m*float((mask>>(lane%8))&1?-1:1);
}
template<int V> struct KK;
template<int V,int MODE>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr size_t blocks=ROWS/R,total=size_t(SLOTS)*blocks;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(total*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
    const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
    const float* xs=x+size_t(slot)*K;float acc[R];const uint8_t* rows[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){acc[i]=0;rows[i]=w+(size_t(expert[slot])*ROWS+first+i)*RB;}
    for(uint32_t block=0;block<K/256;++block){
      #pragma unroll
      for(unsigned i=0;i<R;++i){const auto*packed=rows[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
        #pragma unroll
        for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;
          float weight;if constexpr(MODE==0)weight=element_engine(packed,d,group,lane);else if constexpr(MODE==1)weight=element_variant<true,false>(packed,d,group,lane);else if constexpr(MODE==2)weight=element_variant<false,true>(packed,d,group,lane);else weight=MODE==3?element_variant<true,true>(packed,d,group,lane):element_engine(packed,d,group,lane);
          if constexpr(MODE==4)acc[i]=sycl::fma(weight,xs[k],acc[i]);else{const float product=weight*xs[k];acc[i]=acc[i]+product;}}}
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[size_t(slot)*ROWS+first+i]=sum;}
  });
}
// Lane-contiguous variant: lane l owns group l/4, elements (l%4)*8..+7 of every block. The same per-element weight
// values (same formula); only the F32 summation order differs: per lane, 8 consecutive elements per block, then the tree.
struct K5;
sycl::event run5(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr size_t blocks=ROWS/R,total=size_t(SLOTS)*blocks;
  return q.parallel_for<K5>(sycl::nd_range<1>(total*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
    const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
    const unsigned group=lane/4,chunk=lane%4;
    const float* xs=x+size_t(slot)*K;float acc[R];const uint8_t* rows[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){acc[i]=0;rows[i]=w+(size_t(expert[slot])*ROWS+first+i)*RB;}
    for(uint32_t block=0;block<K/256;++block){
      const uint32_t k0=block*256u+group*32u+chunk*8u;
      const sycl::vec<float,4> xa=*reinterpret_cast<const sycl::vec<float,4>*>(xs+k0),xb=*reinterpret_cast<const sycl::vec<float,4>*>(xs+k0+4);
      #pragma unroll
      for(unsigned i=0;i<R;++i){const auto*packed=rows[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
        const auto*half_words=reinterpret_cast<const uint16_t*>(packed+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16;
        const uint32_t code=(word>>(7*chunk))&127,mask=code|((sycl::popcount(code)%2)<<7);
        const float scale=(d*(0.5f+float(word>>28)))*0.5f;
        const auto*q16=reinterpret_cast<const uint16_t*>(packed+2+group*8);const uint32_t pair=q16[chunk];
        const uint32_t g0=iq3::iq3_grid[pair&255],g1=iq3::iq3_grid[pair>>8];
        #pragma unroll
        for(unsigned j=0;j<8;++j){const uint32_t mag=((j<4?g0:g1)>>(8*(j%4)))&255;
          const float weight=(scale*float(mag))*float((mask>>j)&1?-1:1);
          const float product=weight*(j<4?xa[j]:xb[j-4]);acc[i]=acc[i]+product;}
      }
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[size_t(slot)*ROWS+first+i]=sum;}
  });
}
// Scheduling sweep: RR rows per subgroup, WG lanes per work-group. Each output's arithmetic is the engine replica's
// (same lane mapping, same order), so every point must be bitwise-equal.
template<int RR,int WG> struct KS;
template<int RR,int WG> sycl::event runs(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr size_t blocks=ROWS/RR,total=size_t(SLOTS)*blocks,SGS=WG/32,groups=(total+SGS-1)/SGS;
  return q.parallel_for<KS<RR,WG>>(sycl::nd_range<1>(groups*WG,WG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id()*SGS+sg.get_group_linear_id();
    if(logical>=total)return;
    const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*RR;
    const float* xs=x+size_t(slot)*K;float acc[RR];const uint8_t* rows[RR];
    #pragma unroll
    for(unsigned i=0;i<RR;++i){acc[i]=0;rows[i]=w+(size_t(expert[slot])*ROWS+first+i)*RB;}
    for(uint32_t block=0;block<K/256;++block){
      #pragma unroll
      for(unsigned i=0;i<RR;++i){const auto*packed=rows[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
        #pragma unroll
        for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;
          const float weight=element_engine(packed,d,group,lane);const float product=weight*xs[k];acc[i]=acc[i]+product;}}
    }
    #pragma unroll
    for(unsigned i=0;i<RR;++i){float sum=acc[i];for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[size_t(slot)*ROWS+first+i]=sum;}
  });
}
// Gather diagnostics. G=1: iq3_grid copied into work-group local memory (exact). G=2: no table read at all, magnitude
// from index arithmetic (WRONG values; timing only, to bound what the gather costs).
template<int G> struct KG;
template<int G> sycl::event rung(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned WG=128,SGS=WG/32;constexpr size_t blocks=ROWS/R,total=size_t(SLOTS)*blocks,groups=(total+SGS-1)/SGS;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<uint32_t,1> grid(256,h);
   h.parallel_for<KG<G>>(sycl::nd_range<1>(groups*WG,WG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    if constexpr(G==1){for(unsigned i=it.get_local_linear_id();i<256;i+=WG)grid[i]=iq3::iq3_grid[i];sycl::group_barrier(it.get_group());}
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id()*SGS+sg.get_group_linear_id();
    if(logical>=total)return;
    const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
    const float* xs=x+size_t(slot)*K;float acc[R];const uint8_t* rows[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){acc[i]=0;rows[i]=w+(size_t(expert[slot])*ROWS+first+i)*RB;}
    for(uint32_t block=0;block<K/256;++block){
      #pragma unroll
      for(unsigned i=0;i<R;++i){const auto*b=rows[i]+block*98u;const float d=iq3::half(iq3::u16(b));
        #pragma unroll
        for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;
          const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
          const auto mask=code|((sycl::popcount(code)%2)<<7);const int sign=(mask>>(lane%8))&1?-1:1;
          const uint32_t idx=b[2+group*8+lane/4];uint32_t entry;
          if constexpr(G==1)entry=grid[idx];else entry=idx*0x01010101u;
          const auto mag=(entry>>(8*(lane%4)))&255;
          const float weight=(((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
          const float product=weight*xs[k];acc[i]=acc[i]+product;}}
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[size_t(slot)*ROWS+first+i]=sum;}
   });});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(5);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/256;++b){uint8_t* p=&hw[r*RB+b*98];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);run<0,0>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> cold;
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-34s cold %7.1f us  %s\n",label,cold[25],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("IQ3_XXS gate, 10 x 640 x 2560, 4 rows/subgroup (%.2f MB)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,0>(q,w,e,x,y);},"engine replica (warm-up)");
  time([&]{return run<0,0>(q,w,e,x,y);},"engine replica");
  time([&]{return run<1,1>(q,w,e,x,y);},"sign by XOR");
  time([&]{return run<2,2>(q,w,e,x,y);},"index from 16-bit words");
  time([&]{return run<3,3>(q,w,e,x,y);},"XOR + words");
  // Memory-side diagnostics (engine kernel, bitwise-equal by construction).
  {std::vector<double> warm;for(int i=0;i<60;++i){auto ev=run<0,0>(q,w,e,x,y);ev.wait();if(i>=10)warm.push_back((ev.get_profiling_info<sycl::info::event_profiling::command_end>()-ev.get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
   std::sort(warm.begin(),warm.end());std::printf("  engine replica WARM (no flush)     %7.1f us\n",warm[25]);}
  {std::vector<int> adj{0,1,2,3,4,5,6,7,8,9};auto* ea=sycl::malloc_device<int>(SLOTS,q);q.memcpy(ea,adj.data(),SLOTS*4).wait();
   time([&]{return run<0,0>(q,w,ea,x,y);},"engine, 10 ADJACENT experts");}
  time([&]{return rung<1>(q,w,e,x,y);},"grid in local memory (WG128)");
  time([&]{return rung<2>(q,w,e,x,y);},"NO grid read (timing only)");
  time([&]{return runs<1,32>(q,w,e,x,y);},"sweep R1 WG32");
  time([&]{return runs<2,32>(q,w,e,x,y);},"sweep R2 WG32");
  time([&]{return runs<4,32>(q,w,e,x,y);},"sweep R4 WG32 (engine)");
  time([&]{return runs<8,32>(q,w,e,x,y);},"sweep R8 WG32");
  time([&]{return runs<1,128>(q,w,e,x,y);},"sweep R1 WG128");
  time([&]{return runs<2,128>(q,w,e,x,y);},"sweep R2 WG128");
  time([&]{return runs<4,128>(q,w,e,x,y);},"sweep R4 WG128");
  time([&]{return runs<2,256>(q,w,e,x,y);},"sweep R2 WG256");
  time([&]{return run<4,4>(q,w,e,x,y);},"engine decode + FMA accumulate");
  {double md=0;std::vector<float> f(SLOTS*ROWS);
  time([&]{return run5(q,w,e,x,y);},"lane-contiguous 8 elements");q.memcpy(f.data(),y,f.size()*4).wait();
  for(size_t i=0;i<f.size();++i)md=std::max(md,double(std::fabs(f[i]-ref[i])/(std::fabs(ref[i])+1e-6)));std::printf("  lane-contiguous max relative difference %.3g\n",md);}
  {std::vector<float> f(SLOTS*ROWS);q.memcpy(f.data(),y,f.size()*4).wait();double md=0;for(size_t i=0;i<f.size();++i)md=std::max(md,double(std::fabs(f[i]-ref[i])/(std::fabs(ref[i])+1e-6)));std::printf("  FMA max relative difference %.3g\n",md);}
}
