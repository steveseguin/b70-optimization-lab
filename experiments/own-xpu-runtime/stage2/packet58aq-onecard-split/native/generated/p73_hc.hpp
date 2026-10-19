#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/build/native/p60_math.hpp"
namespace p73hc {
// Two adjacent output rows retain their original 32 logical lanes. Share the
// eight raw BF16 inputs, and issue both rows' packed code/scale reads before
// their independent sums. No decoded bank, new tree, or four-stream subgroup.
inline std::array<float,2> chains(const uint8_t*w,const uint16_t*x,unsigned lane){
 constexpr unsigned rb=320+4*10+2*10;std::array<float,2>sums{};
 for(unsigned k=lane*8;k<320;k+=256){
  uint32_t words[2][2];float scale[2];
  #pragma unroll
  for(unsigned row=0;row<2;++row){const auto*p=w+row*rb;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,2> packed;packed.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(p+k)));
   words[row][0]=packed[0];words[row][1]=packed[1];
#else
   words[row][0]=p49c::load32(p+k);words[row][1]=p49c::load32(p+k+4);
#endif
   scale[row]=iq3::bits_float(p49c::load32(p+320+4*(k/32)));
  }
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  #pragma unroll
  for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=inputs[j];
#else
   uint16_t bits=x[k+j];
#endif
   float input=iq3::bits_float(uint32_t(bits)<<16);
   #pragma unroll
   for(unsigned row=0;row<2;++row){float value=scale[row]*float(iq3::signed8(uint8_t((words[row][j/4]>>(8*(j%4)))&255)));float product=value*input;sums[row]=sums[row]+product;}
  }
 }
 return sums;
}
inline void host(p60::Bound b){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 for(unsigned k=0;k<2560;k+=2){uint16_t gates[2][4];
  for(unsigned s=0;s<4;++s){unsigned r=s*2560+k;float lanes[2][32];
   for(unsigned lane=0;lane<32;++lane){auto v=chains(b.gate_w+r*rb,b.act,lane);for(unsigned row=0;row<2;++row)lanes[row][lane]=v[row];}
   for(unsigned row=0;row<2;++row){gates[row][s]=iq3::bf16_bits(iq3::tree32(lanes[row]));b.gate[r+row]=gates[row][s];}
  }
  for(unsigned row=0;row<2;++row)p60::mix_output(b,k+row,gates[row]);
 }
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(640*256,256)](sycl::handler& h){sycl::local_accessor<uint16_t,1> gates(16,h);
 h.parallel_for(p35_range0,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,stream=sub%4,base=it.get_group_linear_id()*4+(sub/4)*2,r=stream*2560+base;auto sg=it.get_sub_group();
  auto sums=chains(b.gate_w+r*rb,b.act,lane);
  float v0=sums[0],v1=sums[1];
  for(unsigned s=1;s<32;s*=2){float rhs0=sycl::select_from_group(sg,v0,(lane+s)%32),rhs1=sycl::select_from_group(sg,v1,(lane+s)%32);if(lane%(2*s)==0){v0=v0+rhs0;v1=v1+rhs1;}}
  if(!lane){uint16_t y0=iq3::bf16_bits(v0),y1=iq3::bf16_bits(v1);b.gate[r]=y0;b.gate[r+1]=y1;gates[(sub/4)*8+stream]=y0;gates[(sub/4)*8+4+stream]=y1;}
  it.barrier(sycl::access::fence_space::local_space);
  auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
  if(local<4&&*b.active&&!error.load()&&*b.position<b.capacity){unsigned out=it.get_group_linear_id()*4+local;float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+ng::sigmoid(p39::widen(gates[local*4+s]))*p60::get(b.norm,s*2560+out);b.mix[out]=iq3::bf16_bits(sum/4.f);}
 });});
}
#endif
}
