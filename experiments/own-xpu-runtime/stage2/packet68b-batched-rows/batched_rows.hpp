#pragma once
// Packet68b. Two independent ordered accumulators consume each decoded weight.
// No across-row reduction, tensor core, FMA, or changed BF16 boundary.
#include "p49d_small.hpp"
#include "p60_math.hpp"
namespace p68b {
using iq3::Type;
using Base=p49b::Base;
template<Type T> inline std::array<float,2> dense_lane(const uint8_t* w,
 const uint16_t* x0,const uint16_t* x1,unsigned k,unsigned begin,unsigned end,unsigned lane) {
 std::array<float,2> sum{};
 for(unsigned tile=begin+lane*8;tile<end;tile+=256){
  float scale=0;
  if constexpr(T==Type::Q6_K||T==Type::Q8_0)scale=iq3::bits_float(p49bgemv::load32(w+k+4*(tile/(T==Type::Q6_K?16:32))));
  for(unsigned j=0;j<8&&tile+j<end;++j){
   float weight;
   if constexpr(T==Type::Q6_K||T==Type::Q8_0)weight=scale*float(iq3::signed8(w[tile+j]));
   else if constexpr(T==Type::F32)weight=iq3::bits_float(p49bgemv::load32(w+4*(tile+j)));
   else weight=iq3::bits_float(uint32_t(p49bgemv::load16(w+2*(tile+j)))<<16);
   float product0=weight*p39::widen(x0[tile+j]);sum[0]=sum[0]+product0;
   float product1=weight*p39::widen(x1[tile+j]);sum[1]=sum[1]+product1;
  }
 }
 return sum;
}
template<Type T> inline std::array<uint16_t,2> dense_host(const uint8_t*w,const uint16_t*x0,const uint16_t*x1,unsigned k,unsigned split){
 float parts[2][4]{};
 for(unsigned p=0;p<split;++p){auto bounds=iq3::kopt2::bounds(k,p,split);float lanes[2][32];
  for(unsigned lane=0;lane<32;++lane){auto sums=dense_lane<T>(w,x0,x1,k,bounds.first,bounds.second,lane);for(unsigned r=0;r<2;++r)lanes[r][lane]=sums[r];}
  for(unsigned r=0;r<2;++r)parts[r][p]=iq3::tree32(lanes[r]);
 }
 std::array<uint16_t,2> out;for(unsigned r=0;r<2;++r)out[r]=iq3::bf16_bits(split==1?parts[r][0]:(parts[r][0]+parts[r][1])+(parts[r][2]+parts[r][3]));return out;
}
// A tuple keeps the production small-GEMV launch grouping. Every member has
// two activation/output pointers and one weight pointer, bound through owner.
struct DenseShape {unsigned rows=0,k=0,split=0,rb=0;Type type=Type::F32;};
struct DenseBound {const uint8_t*w;const uint16_t*x0,*x1;uint16_t*y0,*y1;};
inline DenseBound dense_bind(std::span<void*const>p,unsigned j){return {static_cast<const uint8_t*>(p[j*5]),static_cast<const uint16_t*>(p[j*5+1]),static_cast<const uint16_t*>(p[j*5+2]),static_cast<uint16_t*>(p[j*5+3]),static_cast<uint16_t*>(p[j*5+4])};}
template<class F> inline auto dense_type(Type t,F f){switch(t){case Type::Q6_K:return f.template operator()<Type::Q6_K>();case Type::Q8_0:return f.template operator()<Type::Q8_0>();case Type::F32:return f.template operator()<Type::F32>();case Type::BF16:return f.template operator()<Type::BF16>();default:throw std::invalid_argument("68b dense type");}}
#ifndef OWN_RT_HOST_ONLY
inline float tree(sycl::sub_group sg,float value){unsigned lane=sg.get_local_linear_id();for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}return value;}
template<Type T> inline void dense_device(DenseShape s,DenseBound b,unsigned row,sycl::nd_item<1>it,float* partial){
 unsigned lane=it.get_local_linear_id()%32,sub=it.get_local_linear_id()/32;
 // Four subgroups cooperate on split4; split1 has four output rows per WG.
 unsigned out=s.split==4?row:row*4+sub,part=s.split==4?sub:0;
 auto bounds=iq3::kopt2::bounds(s.k,part,s.split);std::array<float,2> values{};
 if(out<s.rows)values=dense_lane<T>(b.w+size_t(out)*s.rb,b.x0,b.x1,s.k,bounds.first,bounds.second,lane);
 for(unsigned r=0;r<2;++r){values[r]=tree(it.get_sub_group(),values[r]);if(!lane)partial[r*4+sub]=values[r];}
 it.barrier(sycl::access::fence_space::local_space);
 if(!lane&&out<s.rows&&(s.split==1||!sub))for(unsigned r=0;r<2;++r){auto p=partial+r*4;float v=s.split==1?values[r]:(p[0]+p[1])+(p[2]+p[3]);(r?b.y1:b.y0)[out]=iq3::bf16_bits(v);}
}
#endif
struct DenseKernel final:Base {
 std::array<DenseShape,4> shapes{};unsigned count=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{for(unsigned j=0;j<count;++j){auto b=dense_bind(p,j);auto s=shapes[j];dense_type(s.type,[&]<Type T>(){for(unsigned row=0;row<s.rows;++row){auto y=dense_host<T>(b.w+size_t(row)*s.rb,b.x0,b.x1,s.k,s.split);b.y0[row]=y[0];b.y1[row]=y[1];}});}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto ss=shapes;auto n=count;std::array<DenseBound,4> bs{};unsigned total=0;for(unsigned j=0;j<n;++j){bs[j]=dense_bind(p,j);total+=ss[j].split==4?ss[j].rows:(ss[j].rows+3)/4;}
  return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(8,h);
   h.parallel_for(sycl::nd_range<1>(size_t(total)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned group=it.get_group_linear_id(),j=0;for(;j+1<n;++j){unsigned groups=ss[j].split==4?ss[j].rows:(ss[j].rows+3)/4;if(group<groups)break;group-=groups;}
    auto s=ss[j];auto b=bs[j];auto tmp=partial.template get_multi_ptr<sycl::access::decorated::no>().get();
    switch(s.type){case Type::Q6_K:dense_device<Type::Q6_K>(s,b,group,it,tmp);break;case Type::Q8_0:dense_device<Type::Q8_0>(s,b,group,it,tmp);break;case Type::F32:dense_device<Type::F32>(s,b,group,it,tmp);break;case Type::BF16:dense_device<Type::BF16>(s,b,group,it,tmp);break;default:break;}
   });});
 }
#endif
};
inline integrated::Launch dense(ownrt::Device&d,std::span<const integrated::Matrix>a,std::span<const integrated::Matrix>b,std::span<const unsigned>variants){
 if(a.empty()||a.size()>4||a.size()!=b.size()||a.size()!=variants.size())throw std::invalid_argument("68b tuple size");DenseKernel op;op.count=a.size();std::vector<ownrt::Allocation>ids;
 for(unsigned j=0;j<a.size();++j){auto x=a[j],y=b[j];unsigned v=variants[j],split=(v==1||v==4||v==7)?4:1;
  if(x.w!=y.w||x.type!=y.type||x.columns!=y.columns||x.rows!=y.rows||x.count!=1||y.count!=1||x.experts!=1||y.experts!=1||x.routes||y.routes||x.activation!=Type::BF16||y.activation!=Type::BF16||x.output_type!=Type::BF16||y.output_type!=Type::BF16||x.fp32||y.fp32)throw std::invalid_argument("68b dense pair identity");
  if(x.type!=Type::F32&&x.type!=Type::BF16&&x.type!=Type::Q6_K&&x.type!=Type::Q8_0)throw std::invalid_argument("68b dense format");
  if(!x.rows||!x.columns||x.columns%32||x.columns>17408||(split==4&&x.columns%256))throw std::invalid_argument("68b dense geometry");
  unsigned rb=integrated::arithmetic::row_bytes(x.type,x.columns,v);op.shapes[j]={unsigned(x.rows),unsigned(x.columns),split,rb,x.type};
  std::array row{x.w,x.x,y.x,x.y,y.y};size_t bytes[]={size_t(x.rows)*rb,size_t(x.columns)*2,size_t(x.columns)*2,size_t(x.rows)*2,size_t(x.rows)*2};
  for(unsigned k=0;k<5;++k){const auto&r=d.arena.row(row[k]);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[k]||uintptr_t(r.pointer)%(k==0?4:2))throw std::invalid_argument("68b dense binding");for(unsigned l=0;l<k;++l)if((k>=3||l>=3)&&row[k]==row[l])throw std::invalid_argument("68b dense alias");ids.push_back(row[k]);}
 }
 auto e=d.compute(op,ids,{});return {e,e,1};
}
// Unchanged rounded production epilogue, following paired GEMV output.
struct Tail final:Base {
 p39::Kind kind;unsigned rows,capacity;
 p39::Bound bind(std::span<void*const>p,unsigned r)const {auto at=r*7;p39::Bound b{};b.rows=rows;b.capacity=capacity;b.y=(uint16_t*)p[at];b.out=(uint16_t*)p[at+1];b.other=(const uint16_t*)p[at+2];b.streams=(uint16_t*)p[at+1];b.inject=(const uint16_t*)p[at+2];b.error=(uint32_t*)p[at+3];b.active=(const uint32_t*)p[at+4];b.position=(const uint32_t*)p[at+5];return b;}
 static void row(p39::Bound b,p39::Kind k,unsigned i){
#if defined(__SYCL_DEVICE_ONLY__)
  auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);if(!*b.active||error.load())return;
#else
  if(!*b.active||*b.error)return;
#endif
  if(k!=p39::Kind::attention_combine&&*b.position>=b.capacity){if(!i){
#if defined(__SYCL_DEVICE_ONLY__)
   error.store(1);
#else
   *b.error=1;
#endif
  }return;}
  if(k==p39::Kind::attention_combine)p39::row_tail<p39::Kind::attention_combine>(b,i,b.y[i],0);
  else if(k==p39::Kind::silu_div4)p39::row_tail<p39::Kind::silu_div4>(b,i,b.y[i],0);
  else p39::row_tail<p39::Kind::shared_act>(b,i,b.y[i],0);
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{for(unsigned r=0;r<2;++r){auto b=bind(p,r);for(unsigned i=0;i<rows;++i)row(b,kind,i);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{auto a=bind(p,0),b=bind(p,1);auto k=kind;unsigned n=rows;return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::range<1>(n),[=](sycl::id<1>id){row(a,k,id[0]);row(b,k,id[0]);});});}
#endif
};
} // namespace p68b
