#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#pragma once
// Draft-only symmetric Q4; target never calls this code.
#include "stage2/packet194-expert-diet-engine/p59_draft.hpp"
#include <cfenv>
namespace p83 {
inline constexpr char coverage_sha256[]="3a7edc24aebf0352cd78781f0ed4ae273fa5f606b06c0157b00d0673e579580c";
inline size_t row_bytes(unsigned k){if(!k||k%2)throw std::invalid_argument("p83 even columns");return k/2+4*((k+31)/32);}
inline unsigned rows(unsigned vocab,bool mini,const std::string& choice){
 if(mini)return vocab;
 if(vocab!=248320)throw std::invalid_argument("p83 vocabulary");
 if(choice=="production")return 91392;
 if(choice=="p114-80128")return 80128;
 if(choice=="coverage990")return 80128;
 if(choice=="coverage985")return 74752;
 throw std::invalid_argument("p83 prefix selection");
}
inline std::vector<uint8_t> quantize(iq3::Type type,const uint8_t* raw,unsigned nr,unsigned k){
 if(std::fegetround()!=FE_TONEAREST)throw std::invalid_argument("p83 requires nearest-even");
 auto fmt=iq3::layout(type);if(k%fmt.elements)throw std::invalid_argument("p83 source shape");
 const size_t src=k/fmt.elements*fmt.bytes,rb=row_bytes(k);std::vector<uint8_t> out(nr*rb);
 for(unsigned r=0;r<nr;++r)for(unsigned g=0;g<(k+31)/32;++g){float vals[32]{},maximum=0;
  for(unsigned j=0;j<32&&g*32+j<k;++j){unsigned c=g*32+j;float v=iq3::decode(type,raw+r*src+(c/fmt.elements)*fmt.bytes,c%fmt.elements);if(!std::isfinite(v))throw std::invalid_argument("p83 nonfinite weight");vals[j]=v;maximum=std::max(maximum,std::abs(v));}
  float scale=maximum==0?1.f:maximum/7.f;std::memcpy(out.data()+r*rb+k/2+g*4,&scale,4);
  for(unsigned j=0;j<32&&g*32+j<k;++j){unsigned c=g*32+j;int q=std::clamp(int(std::nearbyint(vals[j]/scale)),-7,7);out[r*rb+c/2]|=uint8_t(q+8)<<(4*(c%2));}
 }return out;
}
inline float value(const uint8_t*w,unsigned k,unsigned c){const auto*s=w+k/2+(c/32)*4;return iq3::bits_float(iq3::u32(s))*float(int((w[c/2]>>(4*(c%2)))&15)-8);}
template<unsigned K> inline float lane(const uint8_t*w,const uint16_t*x,unsigned l){float sum=0;for(unsigned c=l;c<K;c+=32){float product=value(w,K,c)*iq3::bits_float(uint32_t(x[c])<<16);sum=sum+product;}return sum;}
template<unsigned K>struct Head final:p59::Base{
 unsigned rows{};
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);const size_t rb=row_bytes(K);
  for(unsigned r=0;r<rows;++r){float sums[32];for(unsigned l=0;l<32;++l)sums[l]=lane<K>(w+r*rb,x,l);y[r]=iq3::bf16_bits(iq3::tree32(sums));}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto n=rows;const size_t rb=row_bytes(K);
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((size_t(n)+3)/4)*128,128)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),r=it.get_global_linear_id()/32;if(r>=n)return;float sum=lane<K>(w+size_t(r)*rb,x,l);
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);if(l%(2*width)==0)sum=sum+rhs;}
   if(l==0)y[r]=iq3::bf16_bits(sum);
  }));});}
#endif
};
inline integrated::Launch submit(ownrt::Device&d,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,unsigned nr,unsigned k){
 if(!nr||nr>248320||(k!=16&&k!=2560))throw std::invalid_argument("p83 head shape");
 p59::extent(d,w,size_t(nr)*row_bytes(k));p59::extent(d,x,k*2);p59::extent(d,y,nr*2);std::array ids{w,x,y};ownrt::Event e;
 if(k==16){Head<16> op;op.rows=nr;e=d.compute(op,ids,{});}else{Head<2560>op;op.rows=nr;e=d.compute(op,ids,{});}return {e,e,1};
}
}
