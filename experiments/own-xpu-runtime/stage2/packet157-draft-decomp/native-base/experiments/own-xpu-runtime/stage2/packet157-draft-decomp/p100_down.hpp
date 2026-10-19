#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p100_down.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Packet100: byte permutation and workgroup ordering only. Arithmetic is p65 wide64.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/p65_expert.hpp"
#include <string_view>
namespace p100 {
constexpr size_t row_bytes=360,tile_rows=16,tile_bytes=row_bytes*tile_rows;
inline const uint8_t* code_address(const uint8_t* bank,size_t row,unsigned block){return bank+(row/16)*tile_bytes+block*256+(row%16)*16;}
inline const uint8_t* half_address(const uint8_t* bank,size_t row,unsigned block){return bank+(row/16)*tile_bytes+5120+block*32+(row%16)*2;}
inline bool tiled(std::string_view choice){return choice.ends_with("+down-tile16")||choice=="down-tile16";}
inline std::string_view gate_choice(std::string_view choice){
 for(auto suffix:{std::string_view("+down-interleave"),std::string_view("+down-tile16")})if(choice.ends_with(suffix))return choice.substr(0,choice.size()-suffix.size());
 if(choice=="down-interleave"||choice=="down-tile16")return "wide64";
 return choice;
}
// Input consists of already validated p49 packed rows. Every code/scale byte
// is copied exactly once. Destination is separate; no FP operation at load.
inline std::vector<uint8_t> transpose(const uint8_t* src,size_t rows){
 if(!src||!rows||rows%16)throw std::invalid_argument("p100 tile rows");
 std::vector<uint8_t> dst(rows*row_bytes);
 for(size_t row=0;row<rows;++row)for(unsigned block=0;block<20;++block){
  std::memcpy(const_cast<uint8_t*>(code_address(dst.data(),row,block)),src+row*row_bytes+block*16,16);
  std::memcpy(const_cast<uint8_t*>(half_address(dst.data(),row,block)),src+row*row_bytes+320+block*2,2);
 }return dst;
}
inline std::array<float,16> tile_chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned physical){
 constexpr unsigned K=640,V=16;constexpr bool Packed=false;constexpr auto T=iq3::Type::IQ4_NL;
 std::array<float,V> sums{};using p65::RawTile;using p65::decode_tile;
 for(unsigned step=0;step<(K+255)/256;++step){
   static_assert(V==16);
   #pragma unroll
   for(unsigned block_in_lane=0;block_in_lane<V/4;++block_in_lane){
    unsigned first=step*256+8*(physical*V+block_in_lane*4);if(first>=K)continue;
    unsigned block=first/32;uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(code_address(w,source,block))));
    #pragma unroll
    for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
    for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(code_address(w,source,block)+4*i);
#endif
    uint16_t half=p49bgemv::load16(half_address(w,source,block));
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode_tile<T>(t,k,values);
#if defined(__SYCL_DEVICE_ONLY__)
     sycl::vec<uint16_t,8> inputs;
    if constexpr(Packed){
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
      uint16_t bits;if constexpr(Packed){uint32_t packed=p49bgemv::load32(reinterpret_cast<const uint8_t*>(x+k+2*(j/2)));bits=uint16_t(packed>>(16*(j%2)));}else bits=x[k+j];
#endif
      float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
     }
    }
   }
 }return sums;
}
template<unsigned Mode>struct Kernel final:p49b::Base {
 static constexpr auto T=iq3::Type::IQ4_NL;static constexpr unsigned K=640,WG=64;static constexpr bool paired=false;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 static unsigned mapped_group(unsigned group,unsigned rows,unsigned count){
  if constexpr(Mode==1){if(rows%RowsPerGroup==0)return (group%count)*(rows/RowsPerGroup)+group/count;}
  return group;
 }
 static std::array<float,V> chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned lane){
  if constexpr(Mode==2)return tile_chains(w,source,x,lane);
  else return p65::wide_chains<T,K,V>(w+source*row_bytes,x,lane);
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=logical_row(mapped_group(group,rows,count),sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=paired?sub%2:0;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w),source,b.x+(paired?0:slot*K),lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=paired?sub%2:0;
    unsigned logical=logical_row(mapped_group(it.get_group_linear_id(),b.rows,b.count),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w),source,b.x+(paired?0:slot*K),physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   }));
  });
 }
#endif
};
}
