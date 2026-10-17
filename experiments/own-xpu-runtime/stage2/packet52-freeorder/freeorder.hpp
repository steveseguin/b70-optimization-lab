#pragma once
// Original packet52 orders. Format decoding and BF16 epilogues are local-lab
// dependencies. Every sum/product is separate; neither FMA nor atomics reduce.
#include "../packet51-round2/candidate.hpp"
namespace p52 {
using iq3::Type;
struct Order {const char* name;unsigned lanes,accumulators,split;bool local_table;};
inline constexpr std::array<Order,5> orders{{{"row16-v8",16,1,1,false},{"row8-dual-v8",8,2,1,false},{"split4-row16-v8",16,1,4,false},{"row16-dual-local",16,2,1,true},{"row32-quad-v8",32,4,1,false}}};
struct Spec {Type type;unsigned k,rows,count=1,experts=1,rb=0;unsigned epilogue=0;bool paired=false;};
// epilogue: 0 plain, 1 HC SiLU/4, 2 attention combine. Routed status is kept.
struct Bound {Spec s;const uint8_t*w,*peer;const uint16_t*x,*inject;uint16_t*y,*py,*out,*streams;const iq3::Route*routes;uint32_t*status,*peer_status;float*scratch;};
inline void decode8(Spec s,const uint8_t*w,unsigned k,float(&v)[8],const uint16_t*table=nullptr){
 if(s.type==Type::IQ2_S){
  if(!table){p48::decode8<Type::IQ2_S,2560>(w,k,v);return;}
  constexpr auto l=p48::layout(Type::IQ2_S,2560);unsigned block=k/256,i=k%256,q=i/8;
  unsigned pair=p48::load16(w+block*64+q*2),index=(pair&255)|(((w[l.high+block*8+q/4]>>(2*(q%4)))&3)<<8);
  float d=iq3::half(p48::load16(w+l.halves+2*block));float scale=(d*(.5f+float((w[l.scales+block*8+i/32]>>(4*((i/16)%2)))&15)))*.25f;
  unsigned codes=table[index];for(unsigned j=0;j<8;++j){unsigned code=(codes>>(2*j))&3;int mag=code==0?8:code==1?25:43;v[j]=scale*float((pair>>(8+j))&1?-mag:mag);}return;
 }
 if(s.type==Type::IQ4_NL){p48::decode8<Type::IQ4_NL,640>(w,k,v);return;}
 if(s.type==Type::F32){for(unsigned j=0;j<8;++j)v[j]=iq3::bits_float(p48::load32(w+4*(k+j)));return;}
 unsigned group=s.type==Type::Q6_K?16:32;float scale=iq3::bits_float(p48::load32(w+s.k+4*(k/group)));
 uint32_t a=p48::load32(w+k),b=p48::load32(w+k+4);for(unsigned j=0;j<8;++j)v[j]=scale*float(iq3::signed8(uint8_t((j<4?a:b)>>(8*(j%4)))));
}
inline unsigned outputs(Spec s){return s.rows*s.count*(s.paired?2:1);}
inline void locate(Bound b,unsigned logical,unsigned&row,unsigned&slot,unsigned&stream,size_t&source){
 unsigned n=b.s.rows*b.s.count;stream=logical/n;logical%=n;row=logical%b.s.rows;slot=logical/b.s.rows;
 source=(b.s.count>1?size_t(b.routes[slot].expert_id)*b.s.rows+b.routes[slot].row_begin:0)+row;
}
template<Type T,unsigned K> inline void decode_static(const uint8_t*w,unsigned k,float(&v)[8],const uint16_t*table){
 if constexpr(T==Type::IQ2_S){if(table){Spec s{T,K};decode8(s,w,k,v,table);}else p48::decode8<T,K>(w,k,v);}
 else if constexpr(T==Type::IQ4_NL)p48::decode8<T,K>(w,k,v);
 else if constexpr(T==Type::F32){for(unsigned j=0;j<8;++j)v[j]=iq3::bits_float(p48::load32(w+4*(k+j)));}
 else {constexpr unsigned group=T==Type::Q6_K?16:32;float scale=iq3::bits_float(p48::load32(w+K+4*(k/group)));uint32_t a=p48::load32(w+k),b=p48::load32(w+k+4);for(unsigned j=0;j<8;++j)v[j]=scale*float(iq3::signed8(uint8_t((j<4?a:b)>>(8*(j%4)))));}
}
template<unsigned Variant,Type T=Type::F16,unsigned K=0> inline float lane(Bound b,unsigned logical,unsigned lane_id,unsigned part,const uint16_t*table=nullptr){
 constexpr auto o=orders[Variant];
 if constexpr(K){b.s.type=T;b.s.k=K;}
 unsigned row,slot,stream;size_t source;locate(b,logical,row,slot,stream,source);
 auto w=(stream?b.peer:b.w)+source*b.s.rb;auto x=b.x+(b.s.type==Type::IQ4_NL?slot*b.s.k:0);
 // Split in whole eight-value tiles; every tile belongs to exactly one part.
 unsigned tiles=b.s.k/8,begin=(tiles*part/o.split)*8,end=(tiles*(part+1)/o.split)*8;
 float sum[4]{};unsigned iteration=0;
 for(unsigned k=begin+lane_id*8;k<end;k+=o.lanes*8,++iteration){float v[8];if constexpr(K)decode_static<T,K>(w,k,v,table);else decode8(b.s,w,k,v,table);
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> xx;xx.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
  for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
   uint16_t bits=xx[j];
#else
   uint16_t bits=x[k+j];
#endif
   float product=v[j]*iq3::bits_float(uint32_t(bits)<<16);unsigned acc=iteration%o.accumulators;sum[acc]=sum[acc]+product;
  }
 }
 return o.accumulators==1?sum[0]:o.accumulators==2?sum[0]+sum[1]:(sum[0]+sum[1])+(sum[2]+sum[3]);
}
inline void finish(Bound b,unsigned logical,float value,const float*factors=nullptr){unsigned row,slot,stream;size_t source;locate(b,logical,row,slot,stream,source);unsigned n=slot*b.s.rows+row;uint16_t y=iq3::bf16_bits(value);(stream?b.py:b.y)[n]=y;
 if(b.s.count>1&&row==0)(stream?b.peer_status:b.status)[slot]=0;
 if(b.s.epilogue==1)b.out[n]=p39::hc_activation(y);
 if(b.s.epilogue==2)for(unsigned s=0;s<4;++s)b.streams[s*b.s.rows+row]=factors?iq3::bf16_bits(p39::widen(b.streams[s*b.s.rows+row])+p39::widen(y)*factors[s]):p39::combine(b.streams[s*b.s.rows+row],y,b.inject[s]);
}
inline void mirror(Bound b,Order o,bool production=false,unsigned production_split=1){
 // Independent scalar traversal materializes one decoded row, then assigns
 // each scalar product to its registered lane and alternating tile chain.
 // It deliberately does not call the device lane traversal.
 if(production){o.lanes=32;o.accumulators=1;o.split=production_split;o.local_table=false;}
 std::vector<float> decoded(b.s.k),products(b.s.k);
 for(unsigned logical=0;logical<outputs(b.s);++logical){unsigned row,slot,stream;size_t source;locate(b,logical,row,slot,stream,source);auto w=(stream?b.peer:b.w)+source*b.s.rb;auto x=b.x+(b.s.type==Type::IQ4_NL?slot*b.s.k:0);
  for(unsigned tile=0;tile<b.s.k;tile+=8){float values[8];decode8(b.s,w,tile,values);for(unsigned j=0;j<8;++j)decoded[tile+j]=values[j];}
  for(unsigned k=0;k<b.s.k;++k)products[k]=decoded[k]*iq3::bits_float(uint32_t(x[k])<<16);
  float partial[4]{};
  for(unsigned part=0;part<o.split;++part){unsigned begin=(b.s.k/8*part/o.split)*8,end=(b.s.k/8*(part+1)/o.split)*8;
   if(production){auto bounds=iq3::kopt2::bounds(b.s.k,part,o.split);begin=bounds.first;end=bounds.second;}
   float accum[32][4]{};
   for(unsigned k=begin;k<end;++k){unsigned tile=(k-begin)/8,l=tile%o.lanes,chain=(tile/o.lanes)%o.accumulators;accum[l][chain]=accum[l][chain]+products[k];}
   float values[32]{};for(unsigned l=0;l<o.lanes;++l)values[l]=o.accumulators==1?accum[l][0]:o.accumulators==2?accum[l][0]+accum[l][1]:(accum[l][0]+accum[l][1])+(accum[l][2]+accum[l][3]);
   for(unsigned width=1;width<o.lanes;width*=2)for(unsigned l=0;l<o.lanes;l+=2*width)values[l]=values[l]+values[l+width];partial[part]=values[0];
   if(o.split==4&&b.scratch)b.scratch[logical*4+part]=partial[part];
  }
  finish(b,logical,o.split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));
 }
}
template<unsigned V>inline float host_static_lane(Bound b,unsigned logical,unsigned l,unsigned part){auto table=orders[V].local_table&&b.s.type==Type::IQ2_S?p51::iq2_codes.data():nullptr;
 if(b.s.type==Type::IQ2_S&&b.s.k==2560)return lane<V,Type::IQ2_S,2560>(b,logical,l,part,table);
 if(b.s.type==Type::IQ4_NL&&b.s.k==640)return lane<V,Type::IQ4_NL,640>(b,logical,l,part,table);
 if(b.s.type==Type::Q6_K&&b.s.k==2560)return lane<V,Type::Q6_K,2560>(b,logical,l,part,table);
 if(b.s.type==Type::Q6_K&&b.s.k==6144)return lane<V,Type::Q6_K,6144>(b,logical,l,part,table);
 if(b.s.type==Type::Q8_0&&b.s.k==10240)return lane<V,Type::Q8_0,10240>(b,logical,l,part,table);
 if(b.s.type==Type::Q8_0&&b.s.k==320)return lane<V,Type::Q8_0,320>(b,logical,l,part,table);
 if(b.s.type==Type::F32&&b.s.k==2560)return lane<V,Type::F32,2560>(b,logical,l,part,table);
 throw std::invalid_argument("CPU static family");
}
inline float device_lane_host(Bound b,unsigned logical,unsigned l,unsigned part,unsigned variant){switch(variant){case 0:return host_static_lane<0>(b,logical,l,part);case 1:return host_static_lane<1>(b,logical,l,part);case 2:return host_static_lane<2>(b,logical,l,part);case 3:return host_static_lane<3>(b,logical,l,part);case 4:return host_static_lane<4>(b,logical,l,part);default:throw std::invalid_argument("variant");}}
inline void kernel_host(Bound b,unsigned variant){auto o=orders[variant];for(unsigned logical=0;logical<outputs(b.s);++logical){float partial[4]{};for(unsigned p=0;p<o.split;++p){float values[32]{};for(unsigned l=0;l<o.lanes;++l)values[l]=device_lane_host(b,logical,l,p,variant);for(unsigned width=1;width<o.lanes;width*=2)for(unsigned l=0;l<o.lanes;l+=width*2)values[l]=values[l]+values[l+width];partial[p]=values[0];if(o.split==4&&b.scratch)b.scratch[logical*4+p]=values[0];}finish(b,logical,o.split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));}}
// One operation may contain the four production small-FFN tuple members.
// Eleven bindings per member: weight, peer, x, y, py, out, streams, inject,
// routes, status, peer status. Scratch is last.
struct Kernel final:p48b::Base {
 std::array<Spec,4>specs{};unsigned count=1,variant=0,stage=0;
 std::array<Bound,4>bind(std::span<void*const>p)const{std::array<Bound,4>b{};size_t scratch_offset=0;for(unsigned i=0;i<count;++i){auto q=p.data()+i*11;auto&s=specs[i];b[i]={s,(const uint8_t*)q[0],(const uint8_t*)q[1],(const uint16_t*)q[2],(const uint16_t*)q[7],(uint16_t*)q[3],(uint16_t*)q[4],(uint16_t*)q[5],(uint16_t*)q[6],(const iq3::Route*)q[8],(uint32_t*)q[9],(uint32_t*)q[10],(float*)p[count*11]+scratch_offset};scratch_offset+=outputs(s)*4;}return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{if(stage)return;auto b=bind(p);for(unsigned i=0;i<count;++i)kernel_host(b[i],variant);}
#else
 template<unsigned Variant,Type T,unsigned K,bool Tuple=false> sycl::event submit_variant(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const {
  auto bs=bind(p);constexpr auto o=orders[Variant];constexpr bool use_table=o.local_table&&T==Type::IQ2_S;constexpr bool attention=T==Type::Q6_K&&K==6144;unsigned n=count,total=0;for(unsigned i=0;i<n;++i)total+=outputs(specs[i]);unsigned phase=stage;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   sycl::local_accessor<float,1>factors(attention?4:1,h);
   if(phase){h.parallel_for(sycl::nd_range<1>(((size_t(total)+255)/256)*256,256),[=](sycl::nd_item<1>it){
    if constexpr(attention){unsigned local=it.get_local_linear_id();if(local<4)factors[local]=2.f*ng::sigmoid(p39::widen(bs[0].inject[local])/4.f);it.barrier(sycl::access::fence_space::local_space);}
    unsigned logical=it.get_global_linear_id(),which=0;if(logical>=total)return;while(logical>=outputs(bs[which].s))logical-=outputs(bs[which++].s);auto b=bs[which];auto v=b.scratch+logical*4;const float*factor=attention?factors.template get_multi_ptr<sycl::access::decorated::no>().get():nullptr;finish(b,logical,(v[0]+v[1])+(v[2]+v[3]),factor);
   });return;}
   sycl::local_accessor<uint16_t,1>table(use_table?1024:1,h);
   size_t work=((size_t(total)*o.split*o.lanes+255)/256)*256;
   h.parallel_for(sycl::nd_range<1>(work,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    if constexpr(attention&&o.split==1){unsigned local=it.get_local_linear_id();if(local<4)factors[local]=2.f*ng::sigmoid(p39::widen(bs[0].inject[local])/4.f);it.barrier(sycl::access::fence_space::local_space);}
    if(use_table){for(unsigned j=it.get_local_linear_id();j<1024;j+=256)table[j]=p51::iq2_codes[j];it.barrier(sycl::access::fence_space::local_space);}
    unsigned logical=it.get_global_linear_id()/o.lanes,part=logical%o.split;logical/=o.split;unsigned which=0;
    // Padded lanes remain in subgroup collectives (no divergent return).
    bool valid=logical<total;if(valid)while(logical>=outputs(bs[which].s))logical-=outputs(bs[which++].s);
    auto b=bs[which];unsigned l=it.get_local_linear_id()%o.lanes;float value=0;
    const uint16_t*ptr=use_table?table.template get_multi_ptr<sycl::access::decorated::no>().get():nullptr;
    if(valid){if constexpr(Tuple){if(which==0||which==3)value=lane<Variant,Type::F32,2560>(b,logical,l,part,ptr);else value=lane<Variant,Type::Q6_K,2560>(b,logical,l,part,ptr);}else value=lane<Variant,T,K>(b,logical,l,part,ptr);}
    auto sg=it.get_sub_group();unsigned sl=sg.get_local_linear_id();
    for(unsigned width=1;width<o.lanes;width*=2){float rhs=sycl::select_from_group(sg,value,(sl+width)%32);if(l%(2*width)==0)value=value+rhs;}
    if(valid&&!l){if(o.split==1){const float*factor=attention?factors.template get_multi_ptr<sycl::access::decorated::no>().get():nullptr;finish(b,logical,value,factor);}else b.scratch[logical*4+part]=value;}
   });
  });
 }
 template<unsigned V>sycl::event dispatch(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const{
  if(count==4)return submit_variant<V,Type::F32,2560,true>(q,p,deps);
  auto s=specs[0];if(s.type==Type::IQ2_S&&s.k==2560)return submit_variant<V,Type::IQ2_S,2560>(q,p,deps);
  if(s.type==Type::IQ4_NL&&s.k==640)return submit_variant<V,Type::IQ4_NL,640>(q,p,deps);
  if(s.type==Type::Q6_K&&s.k==2560)return submit_variant<V,Type::Q6_K,2560>(q,p,deps);
  if(s.type==Type::Q6_K&&s.k==6144)return submit_variant<V,Type::Q6_K,6144>(q,p,deps);
  if(s.type==Type::Q8_0&&s.k==10240)return submit_variant<V,Type::Q8_0,10240>(q,p,deps);
  if(s.type==Type::Q8_0&&s.k==320)return submit_variant<V,Type::Q8_0,320>(q,p,deps);
  throw std::invalid_argument("unregistered static format/K family");
 }
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{switch(variant){case 0:return dispatch<0>(q,p,deps);case 1:return dispatch<1>(q,p,deps);case 2:return dispatch<2>(q,p,deps);case 3:return dispatch<3>(q,p,deps);case 4:return dispatch<4>(q,p,deps);default:throw std::invalid_argument("variant");}}
#endif
};
}
