#pragma once
#include "p59_hc.hpp"
namespace p122 {
template<unsigned K>struct GateMix final:p59::Base {
 unsigned width;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto n=static_cast<const uint16_t*>(p[3]);auto out=static_cast<uint16_t*>(p[4]);
  // Exceptional CPU values retain the complete unchanged operation. Device
  // fallback below retains the original serial expression for that column.
  auto exceptional=[](uint16_t b){return (b&0x7f80)==0x7f80;};bool special=false;
  for(unsigned i=0;i<K;++i)special|=exceptional(x[i]);
  for(unsigned i=0;i<4*width;++i)special|=exceptional(n[i]);
  for(size_t i=0;i<size_t(4)*width*K;++i){uint16_t b;std::memcpy(&b,w+2*i,2);special|=exceptional(b);}
  if(special){p59::GateMix<K> original;original.width=width;original.run(p);return;}
  for(unsigned col=0;col<width;++col){float products[4];
   for(unsigned stream=0;stream<4;++stream){unsigned row=stream*width+col;float sums[8]{};for(unsigned l=0;l<8;++l)sums[l]=p59::Dense<K,false,false,4,1>::chain(w+size_t(row)*K*2,x,l,0);
    for(unsigned k=1;k<8;k*=2)for(unsigned l=0;l<8;l+=2*k)sums[l]+=sums[l+k];auto value=iq3::bf16_bits(sums[0]);y[row]=value;products[stream]=ng::sigmoid(p59::widen(value))*p59::widen(n[row]);
   }
   float mix=0;for(unsigned stream=0;stream<4;++stream)mix+=products[stream];out[col]=iq3::bf16_bits(mix/4.f);
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto n=static_cast<const uint16_t*>(p[3]);auto out=static_cast<uint16_t*>(p[4]);auto columns=width;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((columns+3)/4)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),lane=local%32,stream=lane/8,physical=lane%8,col=it.get_group_linear_id()*4+local/32,row=stream*columns+col;auto sg=it.get_sub_group();float sum=0;
   if(col<columns)sum=p59::Dense<K,false,false,4,1>::chain(w+size_t(row)*K*2,x,physical,0);
   for(unsigned k=1;k<8;k*=2){float rhs=sycl::select_from_group(sg,sum,stream*8+(physical+k)%8);if(physical%(2*k)==0)sum+=rhs;}
   uint16_t value=iq3::bf16_bits(sum);float product=0;
   if(!physical&&col<columns){y[row]=value;product=ng::sigmoid(p59::widen(value))*p59::widen(n[row]);}
   float products[4];uint16_t gates[4];bool exceptional=false;
   for(unsigned s=0;s<4;++s){products[s]=sycl::select_from_group(sg,product,s*8);gates[s]=sycl::select_from_group(sg,value,s*8);exceptional|=(std::bit_cast<uint32_t>(products[s])&0x7f800000u)==0x7f800000u;}
   if(lane==0&&col<columns){float mix=0;
    if(exceptional){for(unsigned s=0;s<4;++s)mix+=ng::sigmoid(p59::widen(gates[s]))*p59::widen(n[s*columns+col]);}
    else {for(unsigned s=0;s<4;++s)mix+=products[s];}
    out[col]=iq3::bf16_bits(mix/4.f);
   }
  });});
 }
#endif
};
inline integrated::Launch gate_mix(ownrt::Device&d,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation gate,ownrt::Allocation normed,ownrt::Allocation out,unsigned width,unsigned k,bool candidate){
 if(!candidate)return p59::gate_mix(d,w,x,gate,normed,out,width,k);
 p59::extent(d,w,size_t(width)*4*k*2);p59::extent(d,x,k*2);p59::extent(d,gate,width*8);p59::extent(d,normed,width*8);p59::extent(d,out,width*2);std::array ids{w,x,gate,normed,out};
 auto issue=[&]<unsigned K>(){GateMix<K>op;op.width=width;auto e=d.compute(op,ids,{});return integrated::Launch{e,e,1};};
 if(k==320)return issue.template operator()<320>();if(k==4)return issue.template operator()<4>();if(k==8)return issue.template operator()<8>();throw std::invalid_argument("p122 HC low width");
}
}
