#pragma once
#include "case.hpp"
#include "diagnostics.hpp"

namespace expanded_test {
// Like Multiply::run<T>, specialize the expanded format at compile time.
// Keep this separate from the runtime-type packed oracle: inlining changes
// whether the compiler lowers multiplication by a conditional +/-1 to fneg.
template<iq3::Type T> [[gnu::noinline]] float specialized_row(
 const uint8_t* w,const uint16_t* x,size_t k,unsigned split) {
 using namespace iq3;float parts[4]{};
 for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(k,s,split);float lanes[32]{};
  for(unsigned lane=0;lane<32;++lane){
   float sum=0;
   for(size_t tile=lo+lane*8;tile<hi;tile+=256){
    for(unsigned j=0;j<8 && tile+j<hi;++j){
     size_t i=tile+j;float product=expanded::value(T,w,k,i)*bits_float(uint32_t(x[i])<<16);sum=sum+product;
    }
   }
   lanes[lane]=sum;
  }
  parts[s]=tree32(lanes);
 }
 return split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);
}
inline float specialized(iq3::Type t,const uint8_t* w,const uint16_t* x,size_t k,unsigned split) {
#define CASE(T) case iq3::Type::T:return specialized_row<iq3::Type::T>(w,x,k,split)
 switch(t){CASE(Q8_0);CASE(Q3_K);CASE(Q6_K);CASE(IQ3_XXS);CASE(IQ4_NL);CASE(IQ3_S);CASE(IQ2_S);
 default:if(t==iq3::expanded::IQ4_XS)return specialized_row<iq3::expanded::IQ4_XS>(w,x,k,split);}
#undef CASE
 throw std::runtime_error("format specialization");
}
// Independent materialized Python-dequantized weights, same lane and split
// order as the native format test. Keep all finite, signed-zero and NaN bits.
inline float materialized_row(const ExpandedCase& c,const uint16_t* x,unsigned row,unsigned split) {
 using namespace iq3;float parts[4]{};
 for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(c.k,s,split);float lanes[32]{};
  for(unsigned l=0;l<32;++l){
   for(size_t i=lo+l*8;i<hi;i+=256){
    for(unsigned j=0;j<8 && i+j<hi;++j){
     float product=c.values[row*c.k+i+j]*bits_float(uint32_t(x[i+j])<<16);lanes[l]=lanes[l]+product;
    }
   }
  }
  parts[s]=tree32(lanes);
 }
 return split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);
}
inline unsigned format_regression(const ExpandedCase& c,const std::string& name) {
 using namespace iq3;auto ex=expanded::expand(c.type,c.packed.data(),c.packed.size(),c.k);
 auto l=expanded::source_layout(c.type);size_t rb=expanded::row_bytes(c.type,c.k),packed_rb=c.k/l.elements*l.bytes;
 std::vector<uint16_t> x(c.k);for(unsigned i=0;i<c.k;++i)x[i]=bf16_bits(float(int(i%31)-15)/32);
 unsigned count=0;
 for(unsigned split:{1u,4u})for(unsigned row=0;row<c.rows;++row){
  float expected=materialized_row(c,x.data(),row,split);
  if(c.type!=expanded::IQ4_XS){float packed=kopt2::row(c.type,c.packed.data()+row*packed_rb,x.data(),Type::BF16,c.k,
      split==1?kopt2::Variant::wide32:kopt2::Variant::split4);
   auto diff=difference(&packed,&expected,4,4);if(!diff.empty())throw std::runtime_error("packed format oracle "+name+" row="+std::to_string(row)+diff);
  }
  float actual=specialized(c.type,ex.data()+row*rb,x.data(),c.k,split);
  auto diff=difference(&actual,&expected,4,4);
  if(!diff.empty())throw std::runtime_error("specialized format GEMV "+name+" split="+std::to_string(split)+" row="+std::to_string(row)+diff);
  if(bf16_bits(actual)!=bf16_bits(expected))throw std::runtime_error("format BF16");
  float runtime_type=expanded::row(c.type,ex.data()+row*rb,x.data(),Type::BF16,c.k,split);
  diff=difference(&runtime_type,&expected,4,4);
  if(!diff.empty())throw std::runtime_error("runtime-type format GEMV "+name+" row="+std::to_string(row)+diff);
  ++count;
 }
 return count;
}
}
