#pragma once
#include "p60_math.hpp"
namespace p73hc {
// Four adjacent original logical chains share one 32-byte code span and scale.
// Each subgroup owns four adjacent output rows of ONE stream. Streams remain
// separate subgroups, and the packet60 shared-memory mix epilogue is retained.
inline std::array<float,4> chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 std::array<float,4> sums{};
 for(unsigned step=0;step<2;++step){unsigned first=step*256+physical*32;if(first>=320)continue;
  uint32_t codes[8];
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint32_t,8> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+first)));
  #pragma unroll
  for(unsigned i=0;i<8;++i)codes[i]=words[i];
#else
  for(unsigned i=0;i<8;++i)codes[i]=p49c::load32(w+first+4*i);
#endif
  float scale=iq3::bits_float(p49c::load32(w+320+4*(first/32)));
  #pragma unroll
  for(unsigned c=0;c<4;++c){unsigned k=first+c*8;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(uint8_t((codes[c*2+j/4]>>(8*(j%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[k+j];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sums[c]=sums[c]+product;
   }
  }
 }
 return sums;
}
inline bool exceptional(p60::Bound b){for(unsigned j=0;j<320;++j)if((b.act[j]&0x7f80)==0x7f80)return true;return false;}
inline float row(const uint8_t*w,const uint16_t*x){
 float v[8];for(unsigned p=0;p<8;++p){auto c=chains(w,x,p);v[p]=(c[0]+c[1])+(c[2]+c[3]);}
 for(unsigned s=1;s<8;s*=2)for(unsigned p=0;p<8;p+=2*s)v[p]=v[p]+v[p+s];return v[0];
}
inline void host(p60::Bound b){
 if(exceptional(b)){p60::host_gate_mix(b);return;}
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 for(unsigned k=0;k<2560;++k){uint16_t gates[4];for(unsigned s=0;s<4;++s){unsigned r=s*2560+k;gates[s]=iq3::bf16_bits(row(b.gate_w+r*rb,b.act));b.gate[r]=gates[s];}p60::mix_output(b,k,gates);}
}
#ifndef OWN_RT_HOST_ONLY
inline sycl::event device(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&deps){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<uint16_t,1> gates(32,h);sycl::local_accessor<float,1> terms(32,h);
 h.parallel_for(sycl::nd_range<1>(320*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,physical=lane%8,rr=lane/8,stream=sub%4;
  unsigned base=it.get_group_linear_id()*8+(sub/4)*4,k=base+rr,r=stream*2560+k;auto sg=it.get_sub_group();
  bool ex=false;for(unsigned j=lane;j<320;j+=32)ex|=(b.act[j]&0x7f80)==0x7f80;ex=sycl::any_of_group(sg,ex);
  if(ex){for(unsigned c=0;c<4;++c){unsigned out=base+c,idx=stream*2560+out;float v=p49c::dense_lane<iq3::Type::Q8_0,320>(b.gate_w+idx*rb,b.act,0,320,lane);
   for(unsigned s=1;s<32;s*=2){float rhs=sycl::select_from_group(sg,v,(lane+s)%32);if(lane%(2*s)==0)v=v+rhs;}
   if(!lane){uint16_t y=iq3::bf16_bits(v);b.gate[idx]=y;gates[((sub/4)*4+c)*4+stream]=y;}
  }}else{
   auto c=chains(b.gate_w+r*rb,b.act,physical);float v=(c[0]+c[1])+(c[2]+c[3]);
   for(unsigned s=1;s<8;s*=2){float rhs=sycl::select_from_group(sg,v,(lane+s)%32);if(physical%(2*s)==0)v=v+rhs;}
   if(!physical){uint16_t y=iq3::bf16_bits(v);b.gate[r]=y;gates[((sub/4)*4+rr)*4+stream]=y;}
  }
  it.barrier(sycl::access::fence_space::local_space);
  auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
  bool enabled=*b.active&&!error.load()&&*b.position<b.capacity;
  if(local<32&&enabled){unsigned out=it.get_group_linear_id()*8+local/4,s=local%4;terms[local]=ng::sigmoid(p39::widen(gates[local]))*p60::get(b.norm,s*2560+out);}
  it.barrier(sycl::access::fence_space::local_space);
  if(local<8&&enabled){float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+terms[local*4+s];b.mix[it.get_group_linear_id()*8+local]=iq3::bf16_bits(sum/4.f);}

 });});
}
#endif
}
