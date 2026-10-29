#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// Exact MTP draft head split by contiguous vocabulary rows across a rank's two cards (OWNRT_DRAFT_HEAD_SPLIT=1, lab
// 2026-10-29, research/tp/draft-split-2026-10-29). Card c scores rows [offset_c, offset_c + rows_c) with the unchanged
// raw Q6_K row kernel, then takes a local argmax that is ArgmaxFast's scan (adapter.cpp) over its rows, verbatim: one
// 1024-lane work-group, lane l keeps its first maximum over l, l+1024, ... (strict >), then the work-group maximum and
// the lowest index holding it (+0 and -0 equal). It writes a Best record {value bits, global index, error, 0}. One
// direct exchange places both records on both cards; card 0 merges them with the lowest-global-index rule: card 1's
// index wins only if its value is strictly greater (card 0's rows are all below card 1's). That is ArgmaxFast's result
// over the whole prefix for finite logits. Any non-finite logit sets the record's error and the merge fails the draft
// exactly like ArgmaxFast (sticky error, the guess is discarded); the never-read next_token word is then left as it was
// (ArgmaxFast writes its fallback index there). Shared by the device kernels (mtp_kernels.cpp) and the CPU unit test.
#include <algorithm>
#include <bit>
#include <cstdint>
#include <climits>
#include <cmath>
namespace draft_split {
// Per-card split words (u32): [2] ping source, [3] ping sink, [4 + 4 slot .. 8 + 4 slot) the Best record of card `slot`.
inline constexpr unsigned ping_src=2,ping_sink=3,records=4,record_words=4,words=16,lanes=1024;
inline float bf16_value(uint16_t b){return std::bit_cast<float>(uint32_t(b)<<16);}
inline uint32_t float_bits(float f){return std::bit_cast<uint32_t>(f);}
inline float bits_value(uint32_t u){return std::bit_cast<float>(u);}
// Host twins (CPU unit test). shard(): the record a card writes; merge(): card 0's result. Returns false = fail.
inline void shard(const uint16_t* logits,uint32_t rows,uint32_t offset,uint32_t* record){
 int best[lanes];float value[lanes];bool finite=true;
 for(unsigned lane=0;lane<lanes;++lane){best[lane]=-1;value[lane]=0.f;
  for(uint32_t j=lane;j<rows;j+=lanes){const float v=bf16_value(logits[j]);finite=finite&&std::isfinite(v);if(best[lane]<0||v>value[lane]){best[lane]=int(j);value[lane]=v;}}}
 if(!finite){record[0]=0;record[1]=0;record[2]=1;record[3]=0;return;}
 float top=-INFINITY;for(unsigned lane=0;lane<lanes;++lane)if(best[lane]>=0)top=std::fmax(top,value[lane]);
 int index=INT_MAX;for(unsigned lane=0;lane<lanes;++lane)if(best[lane]>=0&&value[lane]==top)index=std::min(index,best[lane]);
 record[0]=float_bits(bf16_value(logits[index]));record[1]=offset+uint32_t(index);record[2]=0;record[3]=0;
}
inline bool merge(const uint32_t* r0,const uint32_t* r1,int32_t& token){
 if(r0[2]||r1[2])return false;
 token=int32_t(bits_value(r1[0])>bits_value(r0[0])?r1[1]:r0[1]);return true;
}
}
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
namespace draft_split {
// Device shard argmax: ArgmaxFast's body (same scan, same reductions) on this card's rows; writes the record.
struct ShardKernel {
 const uint16_t* logits;uint32_t* words;const uint32_t* active;uint32_t* error;uint32_t rows,offset,slot;
 void operator()(sycl::nd_item<1> it)const{
  using ref=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
  const int lane=int(it.get_local_linear_id());auto g=it.get_group();uint32_t* record=words+records+record_words*slot;
  if(!*active)return; // uniform; the draft's active word is always 1
  if(ref(*error).load()){if(lane==0){record[0]=0;record[1]=0;record[2]=1;record[3]=0;}return;} // never a stale record
  const int n=int(rows);int best=-1;float value=0.f;bool finite=true;
  for(int j=lane;j<n;j+=int(lanes)){const float v=bf16_value(logits[j]);finite=finite&&sycl::isfinite(v);if(best<0||v>value){best=j;value=v;}}
  const bool all_finite=sycl::all_of_group(g,finite);
  if(all_finite){
   const float top=sycl::reduce_over_group(g,best<0?-INFINITY:value,sycl::maximum<float>());
   const int index=sycl::reduce_over_group(g,(best>=0&&value==top)?best:INT_MAX,sycl::minimum<int>());
   if(lane==0){record[0]=float_bits(bf16_value(logits[index]));record[1]=offset+uint32_t(index);record[2]=0;record[3]=0;}
  }else if(lane==0){record[0]=0;record[1]=0;record[2]=1;record[3]=0;ref(*error).store(1u);}
 }
};
// Card 0: both records (the peer's arrived by the direct exchange, read here by a later kernel) -> next_token.
struct MergeKernel {
 const uint32_t* words;int32_t* token;const uint32_t* active;uint32_t* error;
 void operator()(sycl::id<1>)const{
  using ref=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
  if(!*active||ref(*error).load())return; // as ArgmaxFast: a failed draft writes nothing
  int32_t t=0;if(!merge(words+records,words+records+record_words,t)){ref(*error).store(1u);return;}
  *token=t;
 }
};
}
#endif
