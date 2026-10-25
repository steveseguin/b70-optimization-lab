// IQ3_XXS routed expert gate (10 slots x 640 rows x K=2560, F32 activations), 4 rows per subgroup: an exact replica of
// the engine's lean BlockRowsOperation<4> loop (k = block*256 + group*32 + lane, block_element_words, product then add,
// adjacent-pair tree) and exact decoder variants. All must be bitwise equal to the replica.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <bit>
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
          float weight;if constexpr(MODE==0)weight=element_engine(packed,d,group,lane);else if constexpr(MODE==1)weight=element_variant<true,false>(packed,d,group,lane);else if constexpr(MODE==2)weight=element_variant<false,true>(packed,d,group,lane);else weight=element_variant<true,true>(packed,d,group,lane);
          const float product=weight*xs[k];acc[i]=acc[i]+product;}}
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
      if(lane==0)y[size_t(slot)*ROWS+first+i]=sum;}
  });
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
}
