#pragma once
#include "p49c_kernel.hpp"
namespace p72 {
// Two adjacent original eight-element chains share one Q6 scale and one raw
// 16-byte code load. Only packed operands are batched; no decoded float buffer.
inline std::array<float,2> chains(const uint8_t* w,const uint16_t* x,unsigned begin,unsigned end,unsigned physical){
 std::array<float,2> sums{};
 for(unsigned k=begin+physical*16;k<end;k+=256){
  float scale=iq3::bits_float(p49c::load32(w+6144+4*(k/16)));
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint32_t,4> codes;codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+k)));
  sycl::vec<uint32_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(x+k)));
#else
  uint32_t codes[4];for(unsigned j=0;j<4;++j)codes[j]=p49c::load32(w+k+4*j);
#endif
  #pragma unroll
  for(unsigned c=0;c<2;++c){
   #pragma unroll
   for(unsigned j=0;j<8;++j){
    unsigned off=c*8+j;
    float value=scale*float(iq3::signed8(uint8_t((codes[off/4]>>(8*(off%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=uint16_t(inputs[off/2]>>(16*(off%2)));
#else
    uint16_t bits=x[k+off];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sums[c]=sums[c]+product;
   }
  }
 }
 return sums;
}
struct AttentionKernel final:p49c::Base {
 p39::Bound shape;
 p39::Bound bind(std::span<void*const>p)const{return p49c::bind_dense(shape,p);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  auto b=bind(p);
  for(unsigned row=0;row<b.rows;++row){float partial[4];
   for(unsigned part=0;part<4;++part){auto bounds=iq3::kopt2::bounds(6144,part,4);float lanes[32];
    for(unsigned physical=0;physical<16;++physical){auto v=chains(b.w+row*b.rb,b.x,bounds.first,bounds.second,physical);lanes[2*physical]=v[0];lanes[2*physical+1]=v[1];}
    partial[part]=iq3::tree32(lanes);
   }
   auto y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));b.y[row]=y;
   p49c::dense_tail_host<p39::Kind::attention_combine>(b,row,y);
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(p);return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(size_t(b.rows)*4*16,64),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned logical=it.get_global_linear_id()/16,row=logical/4,part=logical%4;
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),physical=lane%16;
    auto bounds=iq3::kopt2::bounds(6144,part,4);
    auto values=chains(b.w+row*b.rb,b.x,bounds.first,bounds.second,physical);
    float value=values[0]+values[1];
    for(unsigned width=1;width<16;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(!physical)b.scratch[row*8+part]=value;
   });
  });
 }
#endif
};
}
