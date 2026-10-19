#pragma once
// Packet175b D1: same-bit scale-word multicast inside the dense lane
// (packet140 N1; packet173 LEVER-TABLE D1, site p33::dense_lane and its callers).
//
// Arithmetic is the p68c::dense_lane expression, unchanged: the same tiles in the
// same order, the same FP32 scale bits, the same product and add order, the same
// two ordered accumulators. Only the scale-word load changes.
//
// Baseline: every lane loads its own scale word on every 256-element iteration, so
// adjacent lane pairs (Q6_K, 16-element groups) or quads (Q8_0, 32-element groups)
// load identical bits. D1: on the first iteration of each 32-word chunk, lane L
// loads scale word (chunk_base/group + L) once, predicated to [begin,end) so it
// never reads past the range (or into another row). Each iteration then takes its
// scale bits from the owning lane with an integer subgroup broadcast
// (select_from_group). Q6_K: one load serves 2 iterations; Q8_0: 4 iterations.
//
// Preconditions (checked by the caller, subgroup-uniform): begin % 256 == 0 (every
// kopt2::bounds edge is a multiple of 256), end <= k, k % group == 0. An active lane
// (tile < end) only consumes a word whose index s satisfies s*group <= tile < end,
// so its source lane always loaded it; check_coverage() proves this for every
// registered shape on the CPU.
#include <array>
#include <cstdint>
namespace p175b {
using iq3::Type;
template<Type T> constexpr unsigned group(){static_assert(T==Type::Q6_K||T==Type::Q8_0);return T==Type::Q6_K?16:32;}
template<Type T> constexpr unsigned per_iteration(){return 256/group<T>();}      // distinct scale words per 256 elements
template<Type T> constexpr unsigned iterations_per_chunk(){return 32/per_iteration<T>();}
// The word lane `lane` owns for the chunk starting at element chunk_base (0 = not loaded).
template<Type T> inline uint32_t owned_word(const uint8_t* w,unsigned k,unsigned chunk_base,unsigned end,unsigned lane){
 constexpr unsigned g=group<T>();const unsigned s=chunk_base/g+lane;
 return s*g<end?p49bgemv::load32(w+k+4*s):0u;
}
template<Type T> inline unsigned source_lane(unsigned iteration,unsigned lane){
 return (iteration%iterations_per_chunk<T>())*per_iteration<T>()+lane*8/group<T>();
}
// Fetch(owned_word, source_lane, chunk_base) -> scale bits. Device: select_from_group.
// Host: the exact predicated word the source lane loaded (subgroup emulation).
template<Type T,class Fetch> inline std::array<float,2> dense_lane(const uint8_t* w,const uint16_t* x0,const uint16_t* x1,
 unsigned k,unsigned begin,unsigned end,unsigned lane,Fetch fetch){
 constexpr unsigned chunk=iterations_per_chunk<T>();
 std::array<float,2> sum{};uint32_t owned=0;unsigned iteration=0;
 for(unsigned base=begin;base<end;base+=256,++iteration){
  const unsigned chunk_base=base-(iteration%chunk)*256;
  if(iteration%chunk==0)owned=owned_word<T>(w,k,chunk_base,end,lane);
  const uint32_t bits=fetch(owned,source_lane<T>(iteration,lane),chunk_base);   // every lane participates
  const unsigned tile=base+lane*8;
  if(tile<end){
   float scale=0;scale=iq3::bits_float(bits);
   for(unsigned j=0;j<8&&tile+j<end;++j){
    float weight;weight=scale*float(iq3::signed8(w[tile+j]));
    float product0=weight*p39::widen(x0[tile+j]);sum[0]=sum[0]+product0;
    float product1=weight*p39::widen(x1[tile+j]);sum[1]=sum[1]+product1;
   }
  }
 }
 return sum;
}
// Host subgroup emulation: lane `src` would have loaded owned_word(chunk_base, src).
template<Type T> inline std::array<float,2> host_lane(const uint8_t* w,const uint16_t* x0,const uint16_t* x1,
 unsigned k,unsigned begin,unsigned end,unsigned lane){
 return dense_lane<T>(w,x0,x1,k,begin,end,lane,[&](uint32_t,unsigned src,unsigned chunk_base){return owned_word<T>(w,k,chunk_base,end,src);});
}
// Integer proof: every consumed word was loaded by its source lane, and is the
// baseline's word (tile/group) for that tile. Returns the number of checked tiles.
template<Type T> inline uint64_t check_coverage(unsigned k,unsigned begin,unsigned end){
 constexpr unsigned g=group<T>(),chunk=iterations_per_chunk<T>();uint64_t checked=0;
 if(begin%256||end>k||k%g)return 0;
 for(unsigned lane=0;lane<32;++lane){unsigned iteration=0;
  for(unsigned base=begin;base<end;base+=256,++iteration){
   const unsigned chunk_base=base-(iteration%chunk)*256,src=source_lane<T>(iteration,lane),tile=base+lane*8;
   if(src>=32)return 0;
   if(tile<end){const unsigned s=chunk_base/g+src;if(!(s*g<end)||s!=tile/g)return 0;++checked;}
  }
 }
 return checked;
}
#ifndef OWN_RT_HOST_ONLY
template<Type T> inline std::array<float,2> device_lane(sycl::sub_group sg,const uint8_t* w,const uint16_t* x0,const uint16_t* x1,
 unsigned k,unsigned begin,unsigned end,unsigned lane){
 return dense_lane<T>(w,x0,x1,k,begin,end,lane,[&](uint32_t owned,unsigned src,unsigned){return sycl::select_from_group(sg,owned,src);});
}
#endif
} // namespace p175b
