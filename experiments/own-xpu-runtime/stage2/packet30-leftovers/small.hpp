#pragma once
#include "../packet28-dense/dense.hpp"
#include "../packet27-round2/arithmetic.hpp"
#include <span>
#include <string>
#include <cstring>
#include <tuple>
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
#endif
namespace p30::small {
using iq3::Type;
struct Shape {const char* label;Type type;unsigned rows,cols,split;};
struct Bound {const uint8_t* w{};const uint16_t* x{};uint16_t* y{};size_t weight_bytes{},input_elements{},output_elements{};};
static_assert(sizeof(Bound)*4<=1024);
inline std::vector<Shape> shapes(std::string_view n){
 if(n=="hc.gate")return {{"hc.gate",Type::Q8_0,10240,320,1}};
 if(n=="shexpdown")return {{"shexpdown",Type::Q8_0,2560,640,1}};
 if(n=="small.hc")return {{"hc.low",Type::Q8_0,320,10240,4},{"hc.inject",Type::F32,4,10240,4}};
 if(n=="small.ffn.q6")return {{"router",Type::F32,512,2560,4},{"shexpgate",Type::Q6_K,640,2560,4},{"shexpup",Type::Q6_K,640,2560,4},{"shared_gate",Type::F32,1,2560,4}};
 if(n=="small.ffn.q8")return {{"router",Type::F32,512,2560,4},{"shexpgate",Type::Q8_0,640,2560,1},{"shexpup",Type::Q8_0,640,2560,1},{"shared_gate",Type::F32,1,2560,4}};
 throw std::invalid_argument("p30 small family");
}
inline size_t row_bytes(Shape s){return iq3::expanded::row_bytes(s.type,s.cols);}
inline void validate(std::string_view n,std::span<const Bound> bs,std::string_view variant){
 if(variant!="sg32"&&variant!="rows4")throw std::invalid_argument("p30 small variant");
 auto ss=shapes(n);if(ss.size()!=bs.size())throw std::invalid_argument("p30 small member count");
 for(size_t i=0;i<bs.size();++i){auto b=bs[i];auto s=ss[i];if(!b.w||!b.x||!b.y||b.weight_bytes<size_t(s.rows)*row_bytes(s)||b.input_elements<s.cols||b.output_elements<s.rows)throw std::invalid_argument("p30 small extent");
  for(auto [ptr,len,align]:{std::tuple<const void*,size_t,size_t>{b.w,size_t(s.rows)*row_bytes(s),s.type==Type::F32?4u:1u},{b.x,size_t(s.cols)*2,2},{b.y,size_t(s.rows)*2,2}}){uintptr_t address=reinterpret_cast<uintptr_t>(ptr);if(address%align||len>UINTPTR_MAX-address)throw std::invalid_argument("p30 small alignment/overflow");}
  uintptr_t out=reinterpret_cast<uintptr_t>(b.y);size_t olen=size_t(s.rows)*2;
  for(size_t j=0;j<bs.size();++j){auto q=bs[j];auto t=ss[j];auto overlap=[&](const void* a,size_t len){uintptr_t v=reinterpret_cast<uintptr_t>(a);return out<v+len&&v<out+olen;};
   if(overlap(q.w,size_t(t.rows)*row_bytes(t))||overlap(q.x,size_t(t.cols)*2)||(i!=j&&overlap(q.y,size_t(t.rows)*2)))throw std::invalid_argument("p30 small alias");}
 }
}
template<Type T,unsigned R,unsigned K,unsigned Split> struct Member{
 static constexpr unsigned rows=R,cols=K,split=Split;
 static float lane(const uint8_t* w,const uint16_t* x,unsigned part,unsigned l){auto b=iq3::kopt2::bounds(K,part,Split);return p28::dense_lane<T,K>(w,x,unsigned(b.first),unsigned(b.second),l);}
 static float row(const uint8_t* w,const uint16_t* x){return p28::dense_row<T,K>(w,x,Split);}
};
using Gate=Member<Type::Q8_0,10240,320,1>;using Down=Member<Type::Q8_0,2560,640,1>;
using Low=Member<Type::Q8_0,320,10240,4>;using Inject=Member<Type::F32,4,10240,4>;
using Router=Member<Type::F32,512,2560,4>;using Q6=Member<Type::Q6_K,640,2560,4>;using Q8=Member<Type::Q8_0,640,2560,1>;using Shared=Member<Type::F32,1,2560,4>;
template<class F> void members(std::string_view n,F f){
 if(n=="hc.gate")f.template operator()<Gate>(0);
 else if(n=="shexpdown")f.template operator()<Down>(0);
 else if(n=="small.hc"){f.template operator()<Low>(0);f.template operator()<Inject>(1);}
 else if(n=="small.ffn.q6"){f.template operator()<Router>(0);f.template operator()<Q6>(1);f.template operator()<Q6>(2);f.template operator()<Shared>(3);}
 else if(n=="small.ffn.q8"){f.template operator()<Router>(0);f.template operator()<Q8>(1);f.template operator()<Q8>(2);f.template operator()<Shared>(3);}
 else throw std::invalid_argument("p30 small family");
}
inline void cpu(std::string_view n,std::span<const Bound> bs,std::string_view variant){validate(n,bs,variant);auto ss=shapes(n);members(n,[&]<class M>(size_t j){auto b=bs[j];size_t rb=row_bytes(ss[j]);for(unsigned r=0;r<M::rows;++r)b.y[r]=iq3::bf16_bits(M::row(b.w+r*rb,b.x));});}
// Reusable finite fixture. Packed bytes are retained for an independent oracle.
struct Fixture {std::vector<std::vector<uint8_t>> packed,weights;std::vector<std::vector<uint16_t>> inputs,outputs;std::vector<Bound> bound;
 explicit Fixture(std::string_view n){auto ss=shapes(n);packed.resize(ss.size());weights.resize(ss.size());inputs.resize(ss.size());outputs.resize(ss.size());
  for(size_t j=0;j<ss.size();++j){auto s=ss[j];auto fmt=iq3::layout(s.type);auto& p=packed[j];p.resize(size_t(s.rows)*s.cols/fmt.elements*fmt.bytes);
   for(size_t i=0;i<p.size();++i)p[i]=uint8_t(i*37+17+j);
   for(size_t off=0;off<p.size();off+=fmt.bytes){if(s.type==Type::F32){uint32_t v=0x3b000000u|uint32_t(off&0x7ffff);std::memcpy(p.data()+off,&v,4);}else {size_t at=off+(s.type==Type::Q6_K?208:0);p[at]=0;p[at+1]=0x24;}}
   weights[j]=iq3::expanded::expand(s.type,p.data(),p.size(),s.cols);inputs[j].resize(s.cols);outputs[j].resize(s.rows);for(unsigned k=0;k<s.cols;++k)inputs[j][k]=uint16_t(0x3d00+(k%256));
   bound.push_back({weights[j].data(),inputs[j].data(),outputs[j].data(),weights[j].size(),inputs[j].size(),outputs[j].size()});
  }
 }
};
#ifndef OWN_RT_HOST_ONLY
std::vector<sycl::event> submit(sycl::queue&,std::string_view,std::span<const Bound>,std::string_view,const std::vector<sycl::event>& = {});
#endif
}
