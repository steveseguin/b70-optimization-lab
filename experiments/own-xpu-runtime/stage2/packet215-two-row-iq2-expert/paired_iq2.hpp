#pragma once
#include "selected_cpu.hpp"
#include <array>
#include <span>
#include <stdexcept>
namespace p215 {
using Selected=p58ag_exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true,0,true>;
using Bound=Selected::Bound;
// Counts are stable greedy SLOT-MULTISET matches, including duplicates; they
// are not distinct common expert counts or observed model overlap.
struct MatchPlan {std::array<int,10> row0_to_row1;unsigned pair_count=0,raw_id_overlap=0,tuple_overlap=0;MatchPlan(){row0_to_row1.fill(-1);}};
struct Counters {uint64_t decoded_tiles=0,shared_decoded_tiles=0,independent_decoded_tiles=0,slot_pairs=0,valid_output_rows=0;};
inline void need(bool value,const char* reason){if(!value)throw std::invalid_argument(reason);}
// Internal raw CPU arithmetic interface: the fixture owns complete disjoint
// input/output/status buffers and valid pointer-table backing extents. These
// count/null/geometry checks are not production allocation/alias admission.
inline Bound bind(const Selected& op,std::span<void*const> pointers){
 need(op.rows==640&&op.count==10&&op.experts==512&&op.indirect&&pointers.size()==20,"p215 exact selected indirect geometry");
 auto b=op.bind(pointers);need(b.w&&b.peer&&b.x&&b.y&&b.py&&b.routes&&b.status&&b.peer_status&&b.active&&b.error&&b.halfcache&&b.rb==820,"p215 complete selected CPU bindings");return b;
}
inline bool valid(iq3::Route route){return iq3::valid_route(route,512,640,640);}
inline bool tuple(iq3::Route a,iq3::Route b){return valid(a)&&valid(b)&&a.expert_id==b.expert_id&&a.row_begin==b.row_begin&&a.row_count==b.row_count;}
inline bool compatible(const Bound&a,const Bound&b,unsigned expert){
 if(a.halfcache!=b.halfcache)return false;
 for(auto weights:std::array<std::pair<const uint8_t*,const uint8_t*>,2>{{{a.w,b.w},{a.peer,b.peer}}}){
  const auto&x=reinterpret_cast<const p58::Pointer*>(weights.first)[expert];const auto&y=reinterpret_cast<const p58::Pointer*>(weights.second)[expert];
  if(!x.address||!x.generation||x.address!=y.address||x.generation!=y.generation)return false;
 }return true;
}
inline MatchPlan match_bound(const Bound&a,const Bound&b){MatchPlan plan;std::array<bool,10> raw{},tuples{},used{};
 for(unsigned i=0;i<10;++i){const auto ra=a.routes[i];
  for(unsigned j=0;j<10;++j)if(!raw[j]&&ra.expert_id<512&&ra.expert_id==b.routes[j].expert_id){raw[j]=true;++plan.raw_id_overlap;break;}
  for(unsigned j=0;j<10;++j)if(!tuples[j]&&tuple(ra,b.routes[j])){tuples[j]=true;++plan.tuple_overlap;break;}
  for(unsigned j=0;j<10;++j)if(!used[j]&&tuple(ra,b.routes[j])&&compatible(a,b,ra.expert_id)){used[j]=true;plan.row0_to_row1[i]=int(j);++plan.pair_count;break;}
 }return plan;
}
inline MatchPlan match(const Selected&op,std::span<void*const>a,std::span<void*const>b){return match_bound(bind(op,a),bind(op,b));}
// The selected GNU Host accumulation keeps the accumulator when both inputs
// are quiet NaNs. C++ lets the compiler commute ADDSS operands, and the initial
// paired row1 did so, changing the retained NaN sign. Preserve this selected
// control behavior explicitly, without canonicalizing outputs. Products have
// passed through multiplication and accumulators through addition: both are
// quiet when NaN. Other operands keep the original ordinary addition.
inline float accumulate(float accumulator,float product){
 const uint32_t a=std::bit_cast<uint32_t>(accumulator),b=std::bit_cast<uint32_t>(product);
 if((a&0x7fc00000u)==0x7fc00000u&&(b&0x7fc00000u)==0x7fc00000u)return accumulator;
 return accumulator+product;
}
// Same selected expanded IQ2 layout, decode_tile exceptional path and arithmetic
// order. Each decode feeds one or two independently accumulated V8 chains.
inline std::array<float,2> dot(const uint8_t*w,const uint16_t*x0,const uint16_t*x1,const float*halfcache,Counters&stats){
 constexpr auto layout=p49bgemv::layout(iq3::Type::IQ2_S,2560);float physical_values[2][4]{};
 for(unsigned physical=0;physical<4;++physical){std::array<float,8> sums[2]{};
  for(unsigned step=0;step<10;++step){unsigned first=step*256+8*physical*8;uint32_t codes[4];for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
   uint16_t high=p49bgemv::load16(w+layout.high+step*8+physical*2),scales=p49bgemv::load16(w+layout.scales+step*8+physical*2);
   const auto bits=p49bgemv::load16(w+layout.halves+2*step);const float decoded=halfcache[bits];
   for(unsigned chain=0;chain<8;++chain){unsigned k=first+chain*8;p58ag_exp::RawTile tile;tile.a=(codes[chain/2]>>(16*(chain%2)))&65535;tile.high=(high>>(8*(chain/4)))&255;tile.scale=(scales>>(8*(chain/4)))&255;
    float values[8];p58ag_exp::decode_tile<iq3::Type::IQ2_S>(tile,k,values,decoded);++stats.decoded_tiles;if(x1)++stats.shared_decoded_tiles;else ++stats.independent_decoded_tiles;
    for(unsigned j=0;j<8;++j){float product0=values[j]*iq3::bits_float(uint32_t(x0[k+j])<<16);sums[0][chain]=accumulate(sums[0][chain],product0);
     if(x1){float product1=values[j]*iq3::bits_float(uint32_t(x1[k+j])<<16);sums[1][chain]=accumulate(sums[1][chain],product1);}}
   }
  }
  physical_values[0][physical]=p49dvirtual::local_tree<8>(sums[0]);if(x1)physical_values[1][physical]=p49dvirtual::local_tree<8>(sums[1]);
 }
 for(unsigned input=0;input<(x1?2u:1u);++input)for(unsigned width=1;width<4;width*=2)for(unsigned lane=0;lane<4;lane+=2*width)physical_values[input][lane]=physical_values[input][lane]+physical_values[input][lane+width];
 return {physical_values[0][0],physical_values[1][0]};
}
inline const uint8_t* weight(const Bound&b,unsigned slot,unsigned row,unsigned projection){auto r=b.routes[slot];size_t source=size_t(r.expert_id)*640+r.row_begin+row;return p58::resolve(projection?b.peer:b.w,source*b.rb,size_t(640)*b.rb,true);}
inline void status(const Bound&b,unsigned slot,bool ok){b.status[slot]=!ok;b.peer_status[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
inline void single(const Bound&b,unsigned slot,Counters&stats){auto route=b.routes[slot];bool ok=valid(route);
 for(unsigned projection=0;projection<2;++projection)for(unsigned row=0;row<640;++row){bool active=ok&&row<route.row_count;float value=iq3::bits_float(0x7fc00000);if(active){value=dot(weight(b,slot,row,projection),b.x,nullptr,b.halfcache,stats)[0];++stats.valid_output_rows;}(projection?b.py:b.y)[slot*640+row]=iq3::bf16_bits(value);}
 status(b,slot,ok);
}
inline void paired(const Bound&a,unsigned i,const Bound&b,unsigned j,Counters&stats){auto route=a.routes[i];
 for(unsigned projection=0;projection<2;++projection)for(unsigned row=0;row<640;++row){bool active=row<route.row_count;std::array<float,2> values{iq3::bits_float(0x7fc00000),iq3::bits_float(0x7fc00000)};
  if(active){values=dot(weight(a,i,row,projection),a.x,b.x,a.halfcache,stats);stats.valid_output_rows+=2;}
  (projection?a.py:a.y)[i*640+row]=iq3::bf16_bits(values[0]);(projection?b.py:b.y)[j*640+row]=iq3::bf16_bits(values[1]);
 }status(a,i,true);status(b,j,true);
}
inline void run_pair(const Selected&op,std::span<void*const>p0,std::span<void*const>p1,Counters&stats,bool share=true){auto a=bind(op,p0),b=bind(op,p1);auto plan=match_bound(a,b);stats={};std::array<bool,10> consumed{};
 for(unsigned i=0;i<10;++i){int j=share?plan.row0_to_row1[i]:-1;if(j>=0){paired(a,i,b,unsigned(j),stats);consumed[j]=true;++stats.slot_pairs;}else single(a,i,stats);}
 for(unsigned j=0;j<10;++j)if(!consumed[j])single(b,j,stats);
}
} // namespace p215
