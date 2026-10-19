#pragma once
#include "p49d_route.hpp"
#include <array>

// CPU executable arithmetic specification only. No device kernel, synchronization
// implementation, replacement router GEMV, or claim of a cheaper sorting network.
// Call only after all 512 original GEMV outputs have reached their original
// stored precision. Keep the existing activation after this epilogue unchanged.
namespace p164 {
inline bool better(float x, unsigned xi, float y, unsigned yi) {
  return x > y || (x == y && xi < yi);
}

inline void validate(route42::Args a) {
  using flash::Scalar;
  if(a.n != 512 || a.top != 10 || a.mid != 640 || a.h != 2560 ||
     (a.no != 2 && a.no != 4) || !a.input || !a.scratch || !a.error || !a.active ||
     (a.input_type != Scalar::f32 && a.input_type != Scalar::bf16))
    throw std::invalid_argument("p164 route shape/input");
  // Bounded host specification; device allocation sizes/lifetimes still require
  // the unchanged p49droute::validate admission in any future integration.
  struct Range { uintptr_t begin, end; };
  std::array<Range,8> ranges{};
  unsigned count=0;
  auto add=[&](const void* p, size_t n, size_t alignment) {
    auto b=reinterpret_cast<uintptr_t>(p);
    if(!b || b%alignment || b+n < b)throw std::invalid_argument("p164 pointer");
    for(unsigned i=0;i<count;++i)
      if(b<ranges[i].end && ranges[i].begin<b+n)throw std::invalid_argument("p164 alias");
    ranges[count++]={b,b+n};
  };
  add(a.input,512*(a.input_type==Scalar::f32?4:2),a.input_type==Scalar::f32?4:2);
  add(a.scratch,1088*4,4);add(a.error,4,4);add(a.active,4,4);
  for(unsigned i=0;i<a.no;++i) {
    if(a.output_type[i] != (i==1?Scalar::f32:Scalar::i32))
      throw std::invalid_argument("p164 output type");
    add(a.output[i],(i<2?10:30)*4,4);
  }
}

inline void publish(route42::Args a, std::span<const unsigned> index) {
  if(index.size()!=10)throw std::invalid_argument("p164 selected extent");
  for(unsigned i=0;i<10;++i) {
    if(index[i]>=512)throw std::invalid_argument("p164 invalid expert");
    for(unsigned j=0;j<i;++j)if(index[j]==index[i])throw std::invalid_argument("p164 duplicate expert");
  }
  for(unsigned rank=0;rank<10;++rank)route42::output<512,10>(a,index[rank],rank);
  route42::phase<4,512,10>(a,0);
}

inline void epilogue(route42::Args a) {
  validate(a); // Invalid ABI refuses before any write, including scratch/error.
  for(unsigned chunk=0;chunk<32;++chunk)route42::phase<0,512,10>(a,chunk);
  if(!*a.active || a.failed())return; // No published bytes for nonfinite rows.
  p49c::route_exp_host(a); // Original exp, original adjacent 16-leaf sums.
  float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
  std::array<float,512> probability;
  std::array<unsigned,512> index;
  for(unsigned i=0;i<512;++i) {probability[i]=a.scratch[64+i]/den;index[i]=i;}
  // Same 45-round bitonic network as p78/p109. Ranking logits or exponentials
  // would lose ties introduced by rounded FP32 exp/division.
  for(unsigned size=2;size<=512;size*=2)
    for(unsigned distance=size/2;distance;distance/=2) {
      const auto old=probability;const auto ids=index;
      for(unsigned i=0;i<512;++i) {
        unsigned j=i^distance;
        bool best=((i&size)==0)==((i&distance)==0);
        if(best?better(old[j],ids[j],old[i],ids[i]):better(old[i],ids[i],old[j],ids[j])) {
          probability[i]=old[j];index[i]=ids[j];
        }
      }
    }
  // Validate the complete selected route before publishing any ID/probability
  // or expert descriptor. With finite inputs this is an invariant, not fallback.
  publish(a,std::span<const unsigned>(index.data(),10)); // Original top-10 tree and second division.
}
}
