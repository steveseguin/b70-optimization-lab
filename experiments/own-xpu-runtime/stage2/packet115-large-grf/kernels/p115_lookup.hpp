#pragma once
// Packet99: exact lookup representation/space only; the p65 FP32 chains stay ordered.
#include "../../packet103-record-bundle/p65_expert.hpp"
#include "../../packet103-record-bundle/p90_expert.hpp"
namespace p115lookup {
using iq3::Type;using p65::RawTile;
// Normative magnitudes are exactly 8, 25 and 43. Two bits encode each byte.
consteval auto compact_grid(){
 std::array<uint32_t,512> out{};
 for(unsigned i=0;i<8192;++i){unsigned x=p28::iq2_bytes[i];
  if(x!=8&&x!=25&&x!=43)throw "unexpected IQ2 magnitude";
  out[i/16]|=uint32_t(x==8?0:x==25?1:2)<<(2*(i%16));
 }return out;
}
inline constexpr auto compact=compact_grid();
// level_bank is runtime-inline, so build this from the same normative integer data.
consteval auto make_down(){std::array<uint32_t,128> out{};for(unsigned c=0;c<256;++c)out[c/2]|=(uint32_t(uint8_t(p28::iq4_bytes[c&15]))|(uint32_t(uint8_t(p28::iq4_bytes[c>>4]))<<8))<<(16*(c%2));return out;}
inline constexpr auto down=make_down();
template<unsigned Mode>constexpr unsigned table_words=Mode==1?2048:Mode==2?512:Mode==4?128:1;
template<unsigned Mode>inline uint32_t table_word(unsigned i){if constexpr(Mode==1)return p42expert::iq2_words[i];else if constexpr(Mode==4)return down[i];else return compact[i];}
template<unsigned Mode,Type T,class Lookup>inline void decode_tile(const RawTile&t,unsigned k,float(&v)[8],float d,Lookup table){
 if constexpr(T==Type::IQ2_S){
  unsigned i=k%256,q=i/8,index=(t.a&255)|(((t.high>>(2*(q%4)))&3)<<8),signs=t.a>>8;
  float scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f;
  uint32_t a=0,b=0,packed=0;
  if constexpr(Mode==1){a=table(2*index);b=table(2*index+1);}
  else {uint32_t word;if constexpr(Mode==3)word=compact[index/2];else word=table(index/2);packed=(word>>(16*(index%2)))&65535;}
  bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000||(std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000;
  #pragma unroll
  for(unsigned j=0;j<8;++j){unsigned magnitude;
   if constexpr(Mode==1)magnitude=((j<4?a:b)>>(8*(j%4)))&255;
   else {unsigned code=(packed>>(2*j))&3;magnitude=code==0?8:code==1?25:43;}
   if(exceptional)v[j]=(scale*float(magnitude))*float((signs>>j)&1?-1:1);
   else {int signed_magnitude=(signs>>j)&1?-int(magnitude):int(magnitude);v[j]=scale*float(signed_magnitude);}
  }
 }else{
  unsigned off=k%32;
  #pragma unroll
  for(unsigned j=0;j<8;++j){unsigned code=((j<4?t.a:t.b)>>(8*(j%4)))&255;uint32_t pair=table(code/2)>>(16*(code%2));int level=int(int8_t((pair>>(8*(off/16)))&255));v[j]=d*float(level);}
 }
}
template<unsigned Mode,Type T,unsigned K,unsigned V,bool Cached=false,class Lookup>inline std::array<float,V> wide_chains(const uint8_t*w,const uint16_t*x,unsigned physical,Lookup table){
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
   uint16_t high=p49bgemv::load16(w+l.high+step*8+physical*2);
   uint16_t scales=p49bgemv::load16(w+l.scales+step*8+physical*2);
   uint16_t half=0;float d;if constexpr(Cached)d=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));else {half=p49bgemv::load16(w+l.halves+2*step);d=iq3::half(half);}
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;t.half=half;
    float values[8];decode_tile<Mode,T>(t,k,values,d,table);
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint16_t,8> inputs;
    if constexpr(false){
     sycl::vec<uint32_t,4> packed;
     packed.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(x+k)));
     #pragma unroll
     for(unsigned j=0;j<8;++j)inputs[j]=uint16_t(packed[j/2]>>(16*(j%2)));
    }else inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
    #pragma unroll
    for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
     uint16_t bits=inputs[j];
#else
     uint16_t bits;if constexpr(false){uint32_t packed=p49bgemv::load32(reinterpret_cast<const uint8_t*>(x+k+2*(j/2)));bits=uint16_t(packed>>(16*(j%2)));}else bits=x[k+j];
#endif
     float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
    }
   }
  }else{
   static_assert(V==16);
   #pragma unroll
   for(unsigned block_in_lane=0;block_in_lane<V/4;++block_in_lane){
    unsigned first=step*256+8*(physical*V+block_in_lane*4);if(first>=K)continue;
    unsigned block=first/32;uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+block*16)));
    #pragma unroll
    for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
    for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+block*16+4*i);
#endif
    uint16_t half=p49bgemv::load16(w+l.halves+2*block);
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode_tile<Mode,T>(t,k,values,iq3::half(t.half),table);
#if defined(__SYCL_DEVICE_ONLY__)
     sycl::vec<uint16_t,8> inputs;
    if constexpr(false){
     sycl::vec<uint32_t,4> packed;
     packed.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(x+k)));
     #pragma unroll
     for(unsigned j=0;j<8;++j)inputs[j]=uint16_t(packed[j/2]>>(16*(j%2)));
    }else inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
     #pragma unroll
     for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
      uint16_t bits=inputs[j];
#else
      uint16_t bits;if constexpr(false){uint32_t packed=p49bgemv::load32(reinterpret_cast<const uint8_t*>(x+k+2*(j/2)));bits=uint16_t(packed>>(16*(j%2)));}else bits=x[k+j];
#endif
      float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
     }
    }
   }
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned Mode,bool Cached=false>struct Kernel final:p49b::Base {
 static constexpr unsigned WG=64;
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;auto b=base.bind(p);if constexpr(Cached)b.rb=p90::expert_stride(K);return b;
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 template<class Lookup>static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane,Lookup table){return wide_chains<Mode,T,K,V,Cached>(w,x,lane,table);}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){return chains(w,x,lane,[](unsigned i){return table_word<Mode>(i);});}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=paired?sub%2:0;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   sycl::local_accessor<uint32_t,1> table(sycl::range<1>(table_words<Mode>),h);
   h.parallel_for(sycl::nd_range<1>(size_t(groups)*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    if constexpr(Mode!=3){for(unsigned i=it.get_local_linear_id();i<table_words<Mode>;i+=WG)table[i]=table_word<Mode>(i);it.barrier(sycl::access::fence_space::local_space);}
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=paired?sub%2:0;
    unsigned logical=logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),physical,[=](unsigned i){return table[i];}));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   });
  });
 }
#endif
};
}
