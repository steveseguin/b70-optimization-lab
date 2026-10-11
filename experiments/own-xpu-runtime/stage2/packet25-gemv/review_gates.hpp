#pragma once
#include "fixtures.hpp"
#include <sstream>
namespace p25 {
// This is the CPU analogue of native submit(): special inputs dispatch to the
// shared frozen implementation. It computes a result; it never accepts oracle
// bytes as an argument. The caller separately compares that result to its oracle.
inline std::array<float,2> checked_host_dispatch(Type t,C c,
 const uint8_t* packed,const uint8_t* peer,const uint8_t* expandedw,const uint8_t* expandedp,
 const uint16_t* x,const float* ds,const float* pds,size_t k,unsigned split,bool paired,
 bool* did_fallback=nullptr){
 size_t rb=k/layout(t).elements*layout(t).bytes;
 bool fallback=exceptional(t,packed,rb,x,k)||(paired&&exceptional(t,peer,rb,x,k));
 if(did_fallback)*did_fallback=fallback;
 if(fallback){std::array<float,2> out{};out[0]=reference(t,packed,x,k,split);
  if(paired)out[1]=reference(t,peer,x,k,split);return out;}
 return select_type(t,[&]<Type T>(){return select_candidate(c,[&]<C V>(){
  bool ex=!expert(t)||V==C::staged;
  return host_row<T,V>(ex?expandedw:packed,ex?expandedp:peer,x,ds,pds,k,split,paired);
 });});
}
struct ReviewCounts {size_t decoded_values=0,finite_rows=0,routed_rows=0;};
inline void review_equal(float got,float want,const std::string& label){
 auto a=std::bit_cast<uint32_t>(got),b=std::bit_cast<uint32_t>(want);
 if(a!=b){std::ostringstream out;out<<label<<" got=0x"<<std::hex<<a<<" expected=0x"<<b;throw std::runtime_error(out.str());}
 return;
}
inline ReviewCounts independent_review_gates(){
 ReviewCounts counts;
 for(Type t:{Type::IQ2_S,Type::IQ3_S,Type::IQ3_XXS,Type::IQ4_NL,Type::Q6_K,Type::Q8_0}){
  constexpr size_t k=256;auto f=layout(t);size_t rb=k/f.elements*f.bytes,erb=expanded::row_bytes(t,k),blocks=k/f.elements;
  // Check every dequantized value independently: a NaN earlier in a row cannot
  // mask an incorrect finite value, NaN payload, sign, or signed zero later on.
  for(unsigned special=0;special<2;++special){auto w=seed_weights(t,k,51,special);auto e=expanded::expand(t,w.data(),w.size(),k);
   for(size_t r=0;r<8;++r)for(size_t i=0;i<k;++i){review_equal(expanded::value(t,e.data()+r*erb,k,i),element(t,w.data()+r*rb,i),
    "isolated-decode type="+std::to_string(unsigned(t))+" special="+std::to_string(special)+" row="+std::to_string(r)+" column="+std::to_string(i));++counts.decoded_values;}
  }
  auto w=seed_weights(t,k,0),p=seed_weights(t,k,937),e=expanded::expand(t,w.data(),w.size(),k),ep=expanded::expand(t,p.data(),p.size(),k);
  auto ds=half_scales(t,w),pds=half_scales(t,p);auto x=inputs(k,1,0);bool pair=expert(t)&&t!=Type::IQ4_NL;
  for(unsigned split:{1u,4u})for(size_t r=0;r<8;++r){
   review_equal(reference(t,w.data()+r*rb,x.data(),k,split),scalar_reference(t,w.data()+r*rb,x.data(),k,split),"finite scalar/current type="+std::to_string(unsigned(t)));
   for(C c:candidates(t)){bool fallback=true;auto got=checked_host_dispatch(t,c,w.data()+r*rb,p.data()+r*rb,e.data()+r*erb,ep.data()+r*erb,x.data(),ds.data()+r*blocks,pds.data()+r*blocks,k,split,pair,&fallback);
    if(fallback)throw std::runtime_error("finite review unexpectedly used fallback");
    review_equal(got[0],scalar_reference(t,w.data()+r*rb,x.data(),k,split),"finite candidate/scalar "+std::string(name(c))+" type="+std::to_string(unsigned(t)));
    if(pair)review_equal(got[1],scalar_reference(t,p.data()+r*rb,x.data(),k,split),"finite peer/scalar "+std::string(name(c))+" type="+std::to_string(unsigned(t)));
    ++counts.finite_rows;
   }
  }
 }
 // Run actual routed row arithmetic with distinct slot inputs. Duplicate expert
 // IDs remain in their supplied slots; no route sort, deduplication or merge.
 for(Type t:{Type::IQ2_S,Type::IQ3_S,Type::IQ3_XXS,Type::IQ4_NL})for(unsigned rows:{1u,3u,5u}){
  unsigned k=t==Type::IQ4_NL?640:256;bool pair=t!=Type::IQ4_NL;
  Shape s{"review-route","fixture",t,rows,k,10,1,1,pair};auto w=seed_weights(t,k,0),p=seed_weights(t,k,937);
  auto e=expanded::expand(t,w.data(),w.size(),k),ep=expanded::expand(t,p.data(),p.size(),k);auto ds=half_scales(t,w),pds=half_scales(t,p);auto x=inputs(k,10,0);
  size_t rb=k/layout(t).elements*layout(t).bytes,erb=expanded::row_bytes(t,k),blocks=k/layout(t).elements;
  auto oracle=expected(s,w,p,x);
  for(C c:candidates(t)){std::vector<Result> actual(size_t(rows)*10);std::vector<unsigned> writes(actual.size());
   for(unsigned slot=0;slot<10;++slot)for(unsigned row=0;row<rows;++row){size_t src=(size_t(routes[slot])*rows+row)%8,at=size_t(slot)*rows+row;
    auto got=checked_host_dispatch(t,c,w.data()+src*rb,p.data()+src*rb,e.data()+src*erb,ep.data()+src*erb,x.data()+slot*k,ds.data()+src*blocks,pds.data()+src*blocks,k,1,pair);
    actual[at]=result(got);++writes[at];
   }
   for(size_t at=0;at<actual.size();++at){if(writes[at]!=1||!equal(actual[at],oracle[at]))throw std::runtime_error("routed candidate mismatch "+std::string(name(c))+" type="+std::to_string(unsigned(t))+" rows="+std::to_string(rows)+" slot="+std::to_string(at/rows)+" row="+std::to_string(at%rows));++counts.routed_rows;}
  }
 }
 return counts;
}
}
